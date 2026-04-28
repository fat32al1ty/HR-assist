"""Integration tests for GET /api/users/preferences/suggestions.

T7:  type=role, seeded vacancy_profiles with "Backend Developer" ×3 and
     "Frontend Developer" ×1 → both returned, sorted by frequency desc.
T8:  type=role&q=back → only "Backend Developer" returned (prefix match).
T9:  type=domain with seeded domains in the profile JSON → aggregated results.
T10: unauthenticated request → 401.
T11: two consecutive identical requests → same response (basic smoke for cache).
"""

from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User
from app.models.vacancy import Vacancy
from app.models.vacancy_profile import VacancyProfile

# Wipe the shared in-process cache at module import so prior test runs don't
# pollute these tests.
from app.api.routes import users as _users_module


def _clear_suggestions_cache() -> None:
    with _users_module._suggestions_cache_lock:
        _users_module._suggestions_cache.clear()


def _make_user(db) -> User:
    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"sugg-{suffix}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Suggestions Tester",
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_vacancy(db, *, suffix: str, title: str, source_url: str) -> Vacancy:
    vac = Vacancy(
        source="hh_api",
        source_url=source_url,
        title=title,
        status="indexed",
    )
    db.add(vac)
    db.commit()
    db.refresh(vac)
    return vac


def _make_profile(db, *, vacancy_id: int, role: str, domains: list[str]) -> VacancyProfile:
    vp = VacancyProfile(
        vacancy_id=vacancy_id,
        schema_version="2026-04-16",
        profile={"role": role, "domains": domains},
        canonical_text=role,
        qdrant_collection="test",
        qdrant_point_id=uuid.uuid4().hex,
    )
    db.add(vp)
    db.commit()
    db.refresh(vp)
    return vp


def _auth_headers(email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=email)}"}


class SuggestionsRoleTest(unittest.TestCase):
    """T7 + T8: role suggestions from vacancy_profiles."""

    def setUp(self) -> None:
        _clear_suggestions_cache()
        self.db = SessionLocal()
        self.client = TestClient(app)
        self.suffix = uuid.uuid4().hex[:8]
        self.user = _make_user(self.db)
        self.headers = _auth_headers(self.user.email)
        self.vacancies: list[Vacancy] = []
        self.profiles: list[VacancyProfile] = []

        # Seed namespaced roles so the assertions hold regardless of any
        # other vacancy_profiles already present in the shared test DB.
        # Common prefix `zzrole-{suffix}-` so a single LIKE-prefix query
        # returns only the seeded rows. `zz` keeps it after real values
        # alphabetically — irrelevant for correctness, just hygiene.
        self.role_be = f"zzrole-{self.suffix}-backend"
        self.role_fe = f"zzrole-{self.suffix}-frontend"
        for i in range(3):
            vac = _make_vacancy(
                self.db,
                suffix=self.suffix,
                title=self.role_be,
                source_url=f"https://hh.ru/vacancy/sugg-be-{self.suffix}-{i}",
            )
            self.vacancies.append(vac)
            self.profiles.append(
                _make_profile(self.db, vacancy_id=vac.id, role=self.role_be, domains=[])
            )
        fe_vac = _make_vacancy(
            self.db,
            suffix=self.suffix,
            title=self.role_fe,
            source_url=f"https://hh.ru/vacancy/sugg-fe-{self.suffix}",
        )
        self.vacancies.append(fe_vac)
        self.profiles.append(
            _make_profile(self.db, vacancy_id=fe_vac.id, role=self.role_fe, domains=[])
        )

    def tearDown(self) -> None:
        _clear_suggestions_cache()
        for vp in self.profiles:
            self.db.execute(delete(VacancyProfile).where(VacancyProfile.id == vp.id))
        for vac in self.vacancies:
            self.db.execute(delete(Vacancy).where(Vacancy.id == vac.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    # T7 ─────────────────────────────────────────────────────────────────────
    def test_role_suggestions_returned_sorted_by_frequency(self) -> None:
        """Both seeded roles appear; Backend Developer (freq=3) comes first."""
        resp = self.client.get(
            "/api/users/preferences/suggestions",
            params={"type": "role"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        # Filter by a unique prefix so the seeded namespaced rows are the
        # only ones returned — avoids top-N truncation by a populated DB.
        resp = self.client.get(
            "/api/users/preferences/suggestions",
            params={"type": "role", "q": f"zzrole-{self.suffix}"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        suggestions = resp.json()["suggestions"]
        values = [s["value"] for s in suggestions]
        self.assertIn(self.role_be, values)
        self.assertIn(self.role_fe, values)
        # Higher-frequency item must appear first.
        be_idx = values.index(self.role_be)
        fe_idx = values.index(self.role_fe)
        self.assertLess(be_idx, fe_idx)
        # Frequencies must be reported.
        be_item = next(s for s in suggestions if s["value"] == self.role_be)
        fe_item = next(s for s in suggestions if s["value"] == self.role_fe)
        self.assertEqual(be_item["frequency"], 3)
        self.assertEqual(fe_item["frequency"], 1)

    # T8 ─────────────────────────────────────────────────────────────────────
    def test_role_suggestions_prefix_filters_results(self) -> None:
        """Long unique prefix returns only the namespaced backend role."""
        resp = self.client.get(
            "/api/users/preferences/suggestions",
            params={"type": "role", "q": f"zzrole-{self.suffix}-back"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        suggestions = resp.json()["suggestions"]
        values = [s["value"] for s in suggestions]
        self.assertIn(self.role_be, values)
        self.assertNotIn(self.role_fe, values)


class SuggestionsDomainTest(unittest.TestCase):
    """T9: domain suggestions aggregated from profile.domains JSON array."""

    def setUp(self) -> None:
        _clear_suggestions_cache()
        self.db = SessionLocal()
        self.client = TestClient(app)
        self.suffix = uuid.uuid4().hex[:8]
        self.user = _make_user(self.db)
        self.headers = _auth_headers(self.user.email)
        self.vacancies: list[Vacancy] = []
        self.profiles: list[VacancyProfile] = []

        # Namespace domain names to avoid collision with shared-DB pollution.
        self.dom_ft = f"zzdom-{self.suffix}-fintech"
        self.dom_ht = f"zzdom-{self.suffix}-healthtech"
        for i in range(2):
            vac = _make_vacancy(
                self.db,
                suffix=self.suffix,
                title="Domain Seed Vacancy",
                source_url=f"https://hh.ru/vacancy/sugg-dom-ft-{self.suffix}-{i}",
            )
            self.vacancies.append(vac)
            self.profiles.append(
                _make_profile(
                    self.db, vacancy_id=vac.id, role="Developer", domains=[self.dom_ft]
                )
            )
        ht_vac = _make_vacancy(
            self.db,
            suffix=self.suffix,
            title="HealthTech Vacancy",
            source_url=f"https://hh.ru/vacancy/sugg-dom-ht-{self.suffix}",
        )
        self.vacancies.append(ht_vac)
        self.profiles.append(
            _make_profile(self.db, vacancy_id=ht_vac.id, role="Developer", domains=[self.dom_ht])
        )

    def tearDown(self) -> None:
        _clear_suggestions_cache()
        for vp in self.profiles:
            self.db.execute(delete(VacancyProfile).where(VacancyProfile.id == vp.id))
        for vac in self.vacancies:
            self.db.execute(delete(Vacancy).where(Vacancy.id == vac.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    # T9 ─────────────────────────────────────────────────────────────────────
    def test_domain_suggestions_returns_canonical_taxonomy(self) -> None:
        """type=domain now returns canonical slugs from domain_taxonomy.py,
        not aggregations from vacancy_profiles. The seeded namespaced
        domains (zzdom-...) are NOT in the canonical list and must NOT
        appear; well-known canonical slugs MUST appear with display names.
        """
        resp = self.client.get(
            "/api/users/preferences/suggestions",
            params={"type": "domain", "limit": 50},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        suggestions = resp.json()["suggestions"]
        slugs = [s["value"] for s in suggestions]
        self.assertIn("it", slugs)
        self.assertIn("fintech", slugs)
        self.assertIn("healthcare", slugs)
        self.assertNotIn(self.dom_ft, slugs)  # not canonical
        self.assertNotIn(self.dom_ht, slugs)
        # display_name should be present for canonical entries
        it_item = next(s for s in suggestions if s["value"] == "it")
        self.assertTrue(it_item.get("display_name"))


class SuggestionsAuthAndCacheTest(unittest.TestCase):
    """T10: unauthenticated → 401.  T11: cache smoke — two requests return the same body."""

    def setUp(self) -> None:
        _clear_suggestions_cache()
        self.db = SessionLocal()
        self.client = TestClient(app)
        self.user = _make_user(self.db)
        self.headers = _auth_headers(self.user.email)

    def tearDown(self) -> None:
        _clear_suggestions_cache()
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    # T10 ────────────────────────────────────────────────────────────────────
    def test_suggestions_requires_authentication(self) -> None:
        """No auth header → 401."""
        resp = self.client.get(
            "/api/users/preferences/suggestions",
            params={"type": "role"},
        )
        self.assertEqual(resp.status_code, 401, resp.text)

    # T11 ────────────────────────────────────────────────────────────────────
    def test_suggestions_two_consecutive_requests_return_same_body(self) -> None:
        """Two identical requests return identical JSON (cache smoke)."""
        params = {"type": "role", "q": "python"}
        r1 = self.client.get(
            "/api/users/preferences/suggestions",
            params=params,
            headers=self.headers,
        )
        r2 = self.client.get(
            "/api/users/preferences/suggestions",
            params=params,
            headers=self.headers,
        )
        self.assertEqual(r1.status_code, 200, r1.text)
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertEqual(r1.json(), r2.json())


if __name__ == "__main__":
    unittest.main()
