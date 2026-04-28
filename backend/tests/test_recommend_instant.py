"""Integration tests for POST /api/vacancies/recommend/instant/{resume_id}.

Behaviour under test:
  T1  warm index  → 200, prefetch_empty=False, ≥1 match, responds in <15s
  T2  cold index  → 200, prefetch_empty=True, matches=[]
  T3  bad resume  → 404 for nonexistent and for another user's resume
  T4  no HH/Brave → discover_and_index_vacancies is NOT called by instant
  T5  persistence → instant writes a completed recommendation_jobs row, so
                    GET /recommend/latest returns the same matches/query.
"""

from __future__ import annotations

import time
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.recommendation_job import RecommendationJob
from app.models.resume import Resume
from app.models.user import User
from app.models.user_vacancy_feedback import UserVacancyFeedback
from app.services.vacancy_pipeline import VacancyDiscoveryMetrics

_INSTANT_URL = "/api/vacancies/recommend/instant/{resume_id}"
_BASIC_BODY = {
    "discover_count": 10,
    "match_limit": 10,
    "deep_scan": False,
    "rf_only": True,
    "use_brave_fallback": False,
    "use_prefetched_index": True,
    "discover_if_few_matches": False,
    "min_prefetched_matches": 1,
}


def _auth_header(email: str) -> dict[str, str]:
    token = create_access_token(subject=email)
    return {"Authorization": f"Bearer {token}"}


def _make_user(db, suffix: str) -> User:
    user = User(
        email=f"instant-{suffix}@example.com",
        hashed_password=hash_password("TestPass123"),
        full_name="Instant Test",
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_resume(db, user_id: int, suffix: str) -> Resume:
    resume = Resume(
        user_id=user_id,
        original_filename=f"cv-{suffix}.pdf",
        content_type="application/pdf",
        storage_path=f"/tmp/cv-{suffix}.pdf",
        status="completed",
        analysis={
            "target_role": "Backend Engineer",
            "specialization": "Python",
            "hard_skills": ["Python", "FastAPI"],
            "matching_keywords": ["backend", "python"],
        },
        error_message=None,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


class InstantEndpointWarmIndexTest(unittest.TestCase):
    """T1: warm index returns matches, reports prefetch_empty=False, responds fast."""

    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        suffix = uuid.uuid4().hex[:10]
        self.user = _make_user(self.db, suffix)
        self.resume = _make_resume(self.db, self.user.id, suffix)
        self.headers = _auth_header(self.user.email)

    def tearDown(self) -> None:
        self.db.execute(
            UserVacancyFeedback.__table__.delete().where(
                UserVacancyFeedback.user_id == self.user.id
            )
        )
        self.db.execute(Resume.__table__.delete().where(Resume.id == self.resume.id))
        self.db.execute(User.__table__.delete().where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_instant_returns_matches_when_index_is_warm(self, mock_discover, mock_match) -> None:
        # Pre-populate the matcher stub with one high-quality match so the
        # endpoint sees a non-empty index.
        mock_match.return_value = [
            {
                "vacancy_id": 1,
                "title": "Python Backend Engineer",
                "source_url": "https://hh.ru/vacancy/1",
                "company": "TestCo",
                "location": "Moscow",
                "similarity_score": 0.85,
                "profile": {},
                "tier": "strong",
                "track": "match",
                "track_reason": None,
            }
        ]
        mock_discover.return_value = SimpleNamespace(metrics=VacancyDiscoveryMetrics())

        t0 = time.monotonic()
        resp = self.client.post(
            _INSTANT_URL.format(resume_id=self.resume.id),
            json=_BASIC_BODY,
            headers=self.headers,
        )
        elapsed = time.monotonic() - t0

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertFalse(
            body["prefetch_empty"],
            "prefetch_empty must be False when matches are returned",
        )
        self.assertGreaterEqual(len(body["matches"]), 1)
        # Soft performance assertion: instant endpoint contract says <5s,
        # fail hard only if disgracefully slow.
        if elapsed > 5.0:
            print(f"[WARN] instant endpoint took {elapsed:.2f}s (contract: <5s)")
        self.assertLess(elapsed, 15.0, "instant endpoint took longer than 15s — unacceptable")


class InstantEndpointColdIndexTest(unittest.TestCase):
    """T2: no indexed vacancies → 200 with prefetch_empty=True and empty matches."""

    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        suffix = uuid.uuid4().hex[:10]
        self.user = _make_user(self.db, suffix)
        self.resume = _make_resume(self.db, self.user.id, suffix)
        self.headers = _auth_header(self.user.email)

    def tearDown(self) -> None:
        self.db.execute(
            UserVacancyFeedback.__table__.delete().where(
                UserVacancyFeedback.user_id == self.user.id
            )
        )
        self.db.execute(Resume.__table__.delete().where(Resume.id == self.resume.id))
        self.db.execute(User.__table__.delete().where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_instant_returns_prefetch_empty_true_on_cold_index(
        self, mock_discover, mock_match
    ) -> None:
        # Matcher returns nothing, discovery is irrelevant (instant forces
        # use_prefetched_index=True, discover_if_few_matches=False).
        mock_match.return_value = []
        mock_discover.return_value = SimpleNamespace(
            metrics=VacancyDiscoveryMetrics(fetched=0, indexed=0)
        )

        resp = self.client.post(
            _INSTANT_URL.format(resume_id=self.resume.id),
            json=_BASIC_BODY,
            headers=self.headers,
        )

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(
            body["prefetch_empty"],
            "prefetch_empty must be True when index is cold and no matches returned",
        )
        self.assertEqual(body["matches"], [])


class InstantEndpointAuthorizationTest(unittest.TestCase):
    """T3: 404 for nonexistent resume and for another user's resume."""

    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        self.suffix_a = uuid.uuid4().hex[:10]
        self.suffix_b = uuid.uuid4().hex[:10]
        self.user_a = _make_user(self.db, self.suffix_a)
        self.user_b = _make_user(self.db, self.suffix_b)
        self.resume_b = _make_resume(self.db, self.user_b.id, self.suffix_b)
        # user_a has NO resume so there is no ownership conflict on missing-resume test
        self.headers_a = _auth_header(self.user_a.email)

    def tearDown(self) -> None:
        self.db.execute(Resume.__table__.delete().where(Resume.user_id == self.user_b.id))
        self.db.execute(User.__table__.delete().where(User.id == self.user_a.id))
        self.db.execute(User.__table__.delete().where(User.id == self.user_b.id))
        self.db.commit()
        self.db.close()

    def test_instant_404_for_nonexistent_resume(self) -> None:
        resp = self.client.post(
            _INSTANT_URL.format(resume_id=999999),
            json=_BASIC_BODY,
            headers=self.headers_a,
        )
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_instant_404_for_another_users_resume(self) -> None:
        # user_a requesting user_b's resume must get 404 (not 403 or 200).
        resp = self.client.post(
            _INSTANT_URL.format(resume_id=self.resume_b.id),
            json=_BASIC_BODY,
            headers=self.headers_a,
        )
        self.assertEqual(resp.status_code, 404, resp.text)


class InstantEndpointNoHHBraveTest(unittest.TestCase):
    """T4: discover_and_index_vacancies is never called during an instant request."""

    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        suffix = uuid.uuid4().hex[:10]
        self.user = _make_user(self.db, suffix)
        self.resume = _make_resume(self.db, self.user.id, suffix)
        self.headers = _auth_header(self.user.email)

    def tearDown(self) -> None:
        self.db.execute(
            UserVacancyFeedback.__table__.delete().where(
                UserVacancyFeedback.user_id == self.user.id
            )
        )
        self.db.execute(Resume.__table__.delete().where(Resume.id == self.resume.id))
        self.db.execute(User.__table__.delete().where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    def test_instant_does_not_call_discover_and_index_vacancies(self, mock_match) -> None:
        mock_match.return_value = []

        # Patch discover_and_index_vacancies so that if it IS called the test
        # fails loudly, rather than silently hitting the network.
        def _must_not_be_called(*args, **kwargs):  # type: ignore[return]
            raise AssertionError(
                "discover_and_index_vacancies was called by the instant endpoint — "
                "it must only use the prefetched index."
            )

        with patch(
            "app.services.vacancy_recommendation.discover_and_index_vacancies",
            side_effect=_must_not_be_called,
        ):
            resp = self.client.post(
                _INSTANT_URL.format(resume_id=self.resume.id),
                json=_BASIC_BODY,
                headers=self.headers,
            )

        self.assertEqual(resp.status_code, 200, resp.text)


class InstantEndpointPersistsSnapshotTest(unittest.TestCase):
    """T5: instant writes a completed job so refresh restores the same matches.

    Regression guard for the v0.18.0 bug where Stage 1 instant matches were
    ephemeral, so refresh + restoreRecommendationState resurrected the worse
    Stage 2 deep_scan snapshot and the user's high-quality view disappeared.
    """

    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        suffix = uuid.uuid4().hex[:10]
        self.user = _make_user(self.db, suffix)
        self.resume = _make_resume(self.db, self.user.id, suffix)
        self.headers = _auth_header(self.user.email)

    def tearDown(self) -> None:
        self.db.execute(
            RecommendationJob.__table__.delete().where(RecommendationJob.user_id == self.user.id)
        )
        self.db.execute(
            UserVacancyFeedback.__table__.delete().where(
                UserVacancyFeedback.user_id == self.user.id
            )
        )
        self.db.execute(Resume.__table__.delete().where(Resume.id == self.resume.id))
        self.db.execute(User.__table__.delete().where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_latest_returns_same_matches_as_instant_response(
        self, mock_discover, mock_match
    ) -> None:
        mock_match.return_value = [
            {
                "vacancy_id": 7,
                "title": "Senior Python Engineer",
                "source_url": "https://hh.ru/vacancy/7",
                "company": "PersistCo",
                "location": "Moscow",
                "similarity_score": 0.91,
                "profile": {},
                "tier": "strong",
                "track": "match",
                "track_reason": None,
            },
            {
                "vacancy_id": 8,
                "title": "Backend Developer",
                "source_url": "https://hh.ru/vacancy/8",
                "company": "PersistCo",
                "location": "Remote",
                "similarity_score": 0.78,
                "profile": {},
                "tier": "good",
                "track": "match",
                "track_reason": None,
            },
        ]
        mock_discover.return_value = SimpleNamespace(metrics=VacancyDiscoveryMetrics())

        instant_resp = self.client.post(
            _INSTANT_URL.format(resume_id=self.resume.id),
            json=_BASIC_BODY,
            headers=self.headers,
        )
        self.assertEqual(instant_resp.status_code, 200, instant_resp.text)
        instant_body = instant_resp.json()
        self.assertEqual(len(instant_body["matches"]), 2)

        # Exactly one new completed row was persisted for this user — guards
        # against the test passing vacuously off a stale row from another run.
        row_count = self.db.scalar(
            select(func.count())
            .select_from(RecommendationJob)
            .where(RecommendationJob.user_id == self.user.id)
        )
        self.assertEqual(row_count, 1)

        latest_resp = self.client.get(
            "/api/vacancies/recommend/latest",
            headers=self.headers,
        )
        self.assertEqual(latest_resp.status_code, 200, latest_resp.text)
        latest_body = latest_resp.json()

        self.assertEqual(latest_body["status"], "completed")
        self.assertEqual(latest_body["query"], instant_body["query"])
        instant_ids = [m["vacancy_id"] for m in instant_body["matches"]]
        latest_ids = [m["vacancy_id"] for m in latest_body["matches"]]
        self.assertEqual(latest_ids, instant_ids)

    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_instant_persists_even_when_matches_are_empty(self, mock_discover, mock_match) -> None:
        # Cold-index path also writes a snapshot — otherwise refresh on a
        # cold session resurrects an older deep_scan job and confuses the UI.
        mock_match.return_value = []
        mock_discover.return_value = SimpleNamespace(metrics=VacancyDiscoveryMetrics())

        self.client.post(
            _INSTANT_URL.format(resume_id=self.resume.id),
            json=_BASIC_BODY,
            headers=self.headers,
        )

        row_count = self.db.scalar(
            select(func.count())
            .select_from(RecommendationJob)
            .where(RecommendationJob.user_id == self.user.id)
        )
        self.assertEqual(row_count, 1)

        latest_resp = self.client.get(
            "/api/vacancies/recommend/latest",
            headers=self.headers,
        )
        self.assertEqual(latest_resp.status_code, 200, latest_resp.text)
        latest_body = latest_resp.json()
        self.assertEqual(latest_body["status"], "completed")
        self.assertEqual(latest_body["matches"], [])


if __name__ == "__main__":
    unittest.main()
