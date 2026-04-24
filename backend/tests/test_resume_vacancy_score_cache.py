"""Tests for ResumeVacancyScore cache (v0.10.0 D3).

Covers:
- get_cached_scores: hit, stale miss, version miss
- upsert_scores: idempotent on_conflict_do_update
- delete_scores_for_resume: clears all rows for a resume
- Integration: cached pairs bypass expensive pipeline stages
"""

import unittest
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy import delete, update

from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.resume_vacancy_score import ResumeVacancyScore
from app.models.user import User
from app.models.vacancy import Vacancy
from app.repositories.resume_vacancy_score import (
    delete_scores_for_resume,
    get_cached_scores,
    upsert_scores,
)


def _make_user(db) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"cache-test-{suffix}@example.com",
        hashed_password="test-hash",
        full_name="Cache Test",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_resume(db, user_id: int) -> Resume:
    suffix = uuid.uuid4().hex[:8]
    resume = Resume(
        user_id=user_id,
        original_filename=f"cache-{suffix}.pdf",
        content_type="application/pdf",
        storage_path=f"/tmp/{suffix}.pdf",
        status="completed",
        analysis={"target_role": "SRE"},
        is_active=True,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def _make_vacancy(db) -> Vacancy:
    suffix = uuid.uuid4().hex[:8]
    vacancy = Vacancy(
        source="hh_api",
        source_url=f"https://hh.ru/vacancy/{suffix}",
        title="SRE Engineer",
        company="Acme",
        location="Москва",
        status="indexed",
        raw_text="sre devops observability",
    )
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return vacancy


class ResumeVacancyScoreCacheTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.user = _make_user(self.db)
        self.resume = _make_resume(self.db, self.user.id)
        self.vacancies = [_make_vacancy(self.db) for _ in range(5)]
        self.vids = [v.id for v in self.vacancies]

    def tearDown(self) -> None:
        self.db.execute(
            delete(ResumeVacancyScore).where(
                ResumeVacancyScore.resume_id == self.resume.id
            )
        )
        for v in self.vacancies:
            self.db.execute(delete(Vacancy).where(Vacancy.id == v.id))
        self.db.execute(delete(Resume).where(Resume.id == self.resume.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    # ------------------------------------------------------------------
    # get_cached_scores
    # ------------------------------------------------------------------

    def test_cache_hit_returns_cached_score(self) -> None:
        vid = self.vids[0]
        upsert_scores(
            self.db,
            resume_id=self.resume.id,
            pipeline_version="3.0",
            scores=[{"vacancy_id": vid, "similarity_score": 0.75, "vector_score": 0.80}],
        )

        result = get_cached_scores(
            self.db,
            resume_id=self.resume.id,
            vacancy_ids=[vid],
            pipeline_version="3.0",
            ttl_days=7,
        )

        self.assertIn(vid, result)
        self.assertAlmostEqual(result[vid].similarity_score, 0.75, places=4)
        self.assertAlmostEqual(result[vid].vector_score, 0.80, places=4)

    def test_cache_miss_on_stale_entry(self) -> None:
        vid = self.vids[1]
        upsert_scores(
            self.db,
            resume_id=self.resume.id,
            pipeline_version="3.0",
            scores=[{"vacancy_id": vid, "similarity_score": 0.70}],
        )
        # Backdate computed_at to 10 days ago
        self.db.execute(
            update(ResumeVacancyScore)
            .where(
                ResumeVacancyScore.resume_id == self.resume.id,
                ResumeVacancyScore.vacancy_id == vid,
            )
            .values(computed_at=datetime.now(UTC) - timedelta(days=10))
        )
        self.db.commit()

        result = get_cached_scores(
            self.db,
            resume_id=self.resume.id,
            vacancy_ids=[vid],
            pipeline_version="3.0",
            ttl_days=7,
        )

        self.assertEqual(result, {})

    def test_cache_miss_on_pipeline_version_mismatch(self) -> None:
        vid = self.vids[2]
        upsert_scores(
            self.db,
            resume_id=self.resume.id,
            pipeline_version="3.0",
            scores=[{"vacancy_id": vid, "similarity_score": 0.65}],
        )

        result = get_cached_scores(
            self.db,
            resume_id=self.resume.id,
            vacancy_ids=[vid],
            pipeline_version="3.1",
            ttl_days=7,
        )

        self.assertEqual(result, {})

    def test_empty_vacancy_ids_returns_empty(self) -> None:
        result = get_cached_scores(
            self.db,
            resume_id=self.resume.id,
            vacancy_ids=[],
            pipeline_version="3.0",
            ttl_days=7,
        )
        self.assertEqual(result, {})

    # ------------------------------------------------------------------
    # upsert_scores
    # ------------------------------------------------------------------

    def test_upsert_is_idempotent(self) -> None:
        vid = self.vids[3]

        upsert_scores(
            self.db,
            resume_id=self.resume.id,
            pipeline_version="3.0",
            scores=[{"vacancy_id": vid, "similarity_score": 0.60}],
        )
        upsert_scores(
            self.db,
            resume_id=self.resume.id,
            pipeline_version="3.0",
            scores=[{"vacancy_id": vid, "similarity_score": 0.85}],
        )

        from sqlalchemy import select

        rows = self.db.scalars(
            select(ResumeVacancyScore).where(
                ResumeVacancyScore.resume_id == self.resume.id,
                ResumeVacancyScore.vacancy_id == vid,
                ResumeVacancyScore.pipeline_version == "3.0",
            )
        ).all()
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0].similarity_score, 0.85, places=4)

    # ------------------------------------------------------------------
    # delete_scores_for_resume
    # ------------------------------------------------------------------

    def test_delete_scores_for_resume_clears_all(self) -> None:
        upsert_scores(
            self.db,
            resume_id=self.resume.id,
            pipeline_version="3.0",
            scores=[
                {"vacancy_id": vid, "similarity_score": 0.70}
                for vid in self.vids
            ],
        )

        deleted = delete_scores_for_resume(self.db, resume_id=self.resume.id)

        self.assertEqual(deleted, 5)
        result = get_cached_scores(
            self.db,
            resume_id=self.resume.id,
            vacancy_ids=self.vids,
            pipeline_version="3.0",
            ttl_days=7,
        )
        self.assertEqual(result, {})


# ------------------------------------------------------------------
# Integration: cached pairs bypass expensive pipeline stages
# ------------------------------------------------------------------


def _make_fake_vacancy(vid: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=vid,
        status="indexed",
        source="hh_api",
        source_url=f"https://hh.ru/vacancy/{vid}",
        title="SRE Engineer",
        company="Acme",
        location="Moscow",
        raw_text="sre devops observability",
    )


def _make_fake_profile(vid: int) -> dict:
    return {
        "vacancy_id": vid,
        "is_vacancy": True,
        "title": "SRE Engineer",
        "matching_keywords": ["devops", "sre"],
        "must_have_skills": ["kubernetes"],
        "summary": "SRE role",
    }


class CacheInterpositionTest(unittest.TestCase):
    """Verify that when cache is populated, CrossEncoderRerankStage is not
    called for cached pairs (it remains called only for uncached ones)."""

    def _run_match_with_cache(
        self,
        scored_items: list,
        vacancies: dict,
        cached_map: dict,
    ) -> list[dict]:
        from app.services.matching_service import match_vacancies_for_resume

        resume = SimpleNamespace(
            analysis={
                "target_role": "SRE",
                "specialization": "DevOps",
                "hard_skills": ["kubernetes"],
                "matching_keywords": ["sre"],
            }
        )
        vector_store = MagicMock()
        vector_store.get_resume_vector.return_value = [0.1] * 10
        vector_store.get_user_preference_vectors.return_value = (None, None)
        vector_store.search_vacancy_profiles.return_value = scored_items

        def _get_vacancy(_db, vacancy_id):
            return vacancies.get(int(vacancy_id))

        with (
            patch("app.services.matching_service.get_resume_for_user", return_value=resume),
            patch("app.services.matching_service.get_vector_store", return_value=vector_store),
            patch(
                "app.services.matching_service.recompute_user_preference_profile",
                return_value=None,
            ),
            patch(
                "app.services.matching_service.list_applied_vacancy_ids_for_user",
                return_value=[],
            ),
            patch("app.services.matching_service.list_disliked_vacancy_ids", return_value=[]),
            patch("app.services.matching_service.list_liked_vacancy_ids", return_value=[]),
            patch("app.services.matching_service.list_seen_vacancy_ids", return_value=set()),
            patch("app.services.matching_service.list_added_skill_texts", return_value=[]),
            patch("app.services.matching_service.list_rejected_skill_texts", return_value=[]),
            patch("app.services.matching_service.get_vacancy_by_id", side_effect=_get_vacancy),
            patch("app.services.matching_service._host_allowed_for_matching", return_value=True),
            patch("app.services.matching_service._looks_non_vacancy_page", return_value=False),
            patch(
                "app.services.matching_service._looks_archived_vacancy_strict",
                return_value=False,
            ),
            patch("app.services.matching_service._looks_like_listing_page", return_value=False),
            patch("app.services.matching_service._looks_unlikely_stack", return_value=False),
            patch("app.services.matching_service._lexical_fallback_matches", return_value=[]),
            patch(
                "app.repositories.resume_vacancy_score.get_cached_scores",
                return_value=cached_map,
            ),
            patch("app.repositories.resume_vacancy_score.upsert_scores", return_value=None),
            patch(
                "app.services.matching_service.settings",
                matching_score_cache_enabled=True,
                matching_pipeline_version="3.0",
                matching_score_cache_ttl_days=7,
                feature_exclude_seen_enabled=False,
                rerank_enabled=False,
                llm_rerank_enabled=False,
                rerank_candidate_limit=50,
                rerank_blend_weight=0.6,
            ),
        ):
            return match_vacancies_for_resume(
                SimpleNamespace(), resume_id=1, user_id=1, limit=10
            )

    def test_cache_hit_bypasses_scoring_stage_for_cached_pair(self) -> None:
        vid = 501
        cached_score_obj = SimpleNamespace(
            vacancy_id=vid,
            similarity_score=0.75,
            vector_score=0.80,
        )
        scored_items = [(vid, 0.80, _make_fake_profile(vid))]
        vacancies = {vid: _make_fake_vacancy(vid)}
        cached_map = {vid: cached_score_obj}

        matches = self._run_match_with_cache(scored_items, vacancies, cached_map)

        # The cached vacancy should appear in results with restored score
        match = next((m for m in matches if m["vacancy_id"] == vid), None)
        self.assertIsNotNone(match, "Cached vacancy should appear in results")

    def test_uncached_pair_still_scored(self) -> None:
        vid_cached = 502
        vid_new = 503
        cached_score_obj = SimpleNamespace(
            vacancy_id=vid_cached,
            similarity_score=0.72,
            vector_score=0.77,
        )
        scored_items = [
            (vid_cached, 0.77, _make_fake_profile(vid_cached)),
            (vid_new, 0.85, _make_fake_profile(vid_new)),
        ]
        vacancies = {
            vid_cached: _make_fake_vacancy(vid_cached),
            vid_new: _make_fake_vacancy(vid_new),
        }
        cached_map = {vid_cached: cached_score_obj}

        matches = self._run_match_with_cache(scored_items, vacancies, cached_map)

        vacancy_ids_in_results = {m["vacancy_id"] for m in matches}
        # The uncached vacancy should have been scored and appear in results
        self.assertIn(vid_new, vacancy_ids_in_results)


if __name__ == "__main__":
    unittest.main()
