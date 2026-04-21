"""Hard-filter + soft-boost tests for Phase 2.0 matcher PR."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.matching_service import (
    _hard_filter_drop_reason,
    _location_matches_home,
    _normalize_remote_policy,
    _preferred_title_match,
    _resolve_user_preferences,
    match_vacancies_for_resume,
)


class NormalizeRemotePolicyTest(unittest.TestCase):
    def test_recognises_remote_variants(self) -> None:
        for value in ("remote", "Remote", "удалённо", "удаленная работа", "дистанционно"):
            self.assertEqual(_normalize_remote_policy(value), "remote")

    def test_recognises_hybrid_variants(self) -> None:
        for value in ("hybrid", "Гибрид", "частично удалённо"):
            self.assertEqual(_normalize_remote_policy(value), "hybrid")

    def test_recognises_office_variants(self) -> None:
        for value in ("office", "onsite", "В офисе", "очно"):
            self.assertEqual(_normalize_remote_policy(value), "office")

    def test_unknown_value_is_unclear(self) -> None:
        self.assertEqual(_normalize_remote_policy("mystery"), "unclear")
        self.assertEqual(_normalize_remote_policy(None), "unclear")
        self.assertEqual(_normalize_remote_policy(""), "unclear")


class LocationMatchesHomeTest(unittest.TestCase):
    def test_exact_match(self) -> None:
        self.assertTrue(_location_matches_home("Москва", "Москва"))

    def test_city_prefix_stripped(self) -> None:
        self.assertTrue(_location_matches_home("г. Москва, Россия", "Москва"))

    def test_substring_match(self) -> None:
        self.assertTrue(_location_matches_home("Москва, Россия", "москва"))

    def test_different_city_does_not_match(self) -> None:
        self.assertFalse(_location_matches_home("Санкт-Петербург", "Москва"))

    def test_empty_inputs(self) -> None:
        self.assertFalse(_location_matches_home("", "Москва"))
        self.assertFalse(_location_matches_home("Москва", ""))
        self.assertFalse(_location_matches_home(None, "Москва"))


class ResolveUserPreferencesTest(unittest.TestCase):
    def test_uses_user_values_when_no_overrides(self) -> None:
        user = SimpleNamespace(
            preferred_work_format="remote",
            relocation_mode="home_only",
            home_city="Москва",
            preferred_titles=["Senior Backend"],
        )
        prefs = _resolve_user_preferences(user, None)
        self.assertEqual(prefs["preferred_work_format"], "remote")
        self.assertEqual(prefs["home_city"], "Москва")
        self.assertEqual(prefs["preferred_titles"], ["Senior Backend"])

    def test_overrides_win_over_user_values(self) -> None:
        user = SimpleNamespace(
            preferred_work_format="remote",
            relocation_mode="home_only",
            home_city="Москва",
            preferred_titles=["Senior Backend"],
        )
        prefs = _resolve_user_preferences(
            user,
            {"preferred_work_format": "any", "relocation_mode": "any_city"},
        )
        self.assertEqual(prefs["preferred_work_format"], "any")
        self.assertEqual(prefs["relocation_mode"], "any_city")

    def test_missing_user_falls_back_to_defaults(self) -> None:
        prefs = _resolve_user_preferences(None, None)
        self.assertEqual(prefs["preferred_work_format"], "any")
        self.assertEqual(prefs["relocation_mode"], "home_only")
        self.assertIsNone(prefs["home_city"])
        self.assertEqual(prefs["preferred_titles"], [])

    def test_blank_override_strings_are_ignored(self) -> None:
        user = SimpleNamespace(
            preferred_work_format="office",
            relocation_mode="home_only",
            home_city="Москва",
            preferred_titles=[],
        )
        prefs = _resolve_user_preferences(
            user,
            {"preferred_work_format": "   ", "home_city": "   "},
        )
        # Blank format ignored, home_city empty override clears.
        self.assertEqual(prefs["preferred_work_format"], "office")
        self.assertIsNone(prefs["home_city"])


class HardFilterDropReasonTest(unittest.TestCase):
    def _prefs(self, **kwargs: object) -> dict[str, object]:
        base = {
            "preferred_work_format": "any",
            "relocation_mode": "home_only",
            "home_city": None,
            "preferred_titles": [],
        }
        base.update(kwargs)
        return base

    def test_any_format_never_drops_on_format(self) -> None:
        reason = _hard_filter_drop_reason(
            vacancy_profile={"remote_policy": "office"},
            vacancy_location="Москва",
            prefs=self._prefs(preferred_work_format="any", home_city="Москва"),
        )
        self.assertIsNone(reason)

    def test_remote_pref_drops_office_vacancy(self) -> None:
        reason = _hard_filter_drop_reason(
            vacancy_profile={"remote_policy": "office"},
            vacancy_location="Москва",
            prefs=self._prefs(preferred_work_format="remote", home_city="Москва"),
        )
        self.assertEqual(reason, "work_format")

    def test_office_pref_drops_remote_vacancy(self) -> None:
        reason = _hard_filter_drop_reason(
            vacancy_profile={"remote_policy": "remote"},
            vacancy_location="Москва",
            prefs=self._prefs(preferred_work_format="office", home_city="Москва"),
        )
        self.assertEqual(reason, "work_format")

    def test_unclear_policy_passes(self) -> None:
        reason = _hard_filter_drop_reason(
            vacancy_profile={"remote_policy": "unclear"},
            vacancy_location="Москва",
            prefs=self._prefs(preferred_work_format="remote", home_city="Москва"),
        )
        self.assertIsNone(reason)

    def test_missing_policy_passes_conservatively(self) -> None:
        reason = _hard_filter_drop_reason(
            vacancy_profile={},
            vacancy_location="Москва",
            prefs=self._prefs(preferred_work_format="remote", home_city="Москва"),
        )
        self.assertIsNone(reason)

    def test_geo_filter_drops_wrong_city(self) -> None:
        reason = _hard_filter_drop_reason(
            vacancy_profile={"remote_policy": "office"},
            vacancy_location="Санкт-Петербург",
            prefs=self._prefs(home_city="Москва"),
        )
        self.assertEqual(reason, "geo")

    def test_geo_filter_passes_when_remote(self) -> None:
        reason = _hard_filter_drop_reason(
            vacancy_profile={"remote_policy": "remote"},
            vacancy_location="Санкт-Петербург",
            prefs=self._prefs(home_city="Москва"),
        )
        self.assertIsNone(reason)

    def test_geo_filter_passes_for_matching_city(self) -> None:
        reason = _hard_filter_drop_reason(
            vacancy_profile={"remote_policy": "office"},
            vacancy_location="г. Москва, Россия",
            prefs=self._prefs(home_city="Москва"),
        )
        self.assertIsNone(reason)

    def test_geo_filter_skipped_when_any_city(self) -> None:
        reason = _hard_filter_drop_reason(
            vacancy_profile={"remote_policy": "office"},
            vacancy_location="Санкт-Петербург",
            prefs=self._prefs(relocation_mode="any_city", home_city="Москва"),
        )
        self.assertIsNone(reason)

    def test_geo_filter_skipped_when_no_home_city(self) -> None:
        reason = _hard_filter_drop_reason(
            vacancy_profile={"remote_policy": "office"},
            vacancy_location="Санкт-Петербург",
            prefs=self._prefs(home_city=None),
        )
        self.assertIsNone(reason)

    def test_geo_filter_uses_profile_location_fallback(self) -> None:
        # Row has no location; profile dict does.
        reason = _hard_filter_drop_reason(
            vacancy_profile={"remote_policy": "office", "location": "Санкт-Петербург"},
            vacancy_location=None,
            prefs=self._prefs(home_city="Москва"),
        )
        self.assertEqual(reason, "geo")


class PreferredTitleMatchTest(unittest.TestCase):
    def test_substring_case_insensitive(self) -> None:
        self.assertTrue(
            _preferred_title_match("Senior Backend Engineer", ["senior backend"]),
        )

    def test_no_titles_returns_false(self) -> None:
        self.assertFalse(_preferred_title_match("Senior Backend Engineer", []))

    def test_non_matching_title(self) -> None:
        self.assertFalse(
            _preferred_title_match("Frontend Developer", ["senior backend"]),
        )

    def test_punctuation_is_normalised(self) -> None:
        self.assertTrue(
            _preferred_title_match(
                "Senior Back-end / Platform Engineer",
                ["senior backend"],
            )
        )


class MatchingHardFilterIntegrationTest(unittest.TestCase):
    """End-to-end: feed a fake vector store result and check the matcher respects prefs."""

    def _make_context(
        self,
        *,
        user,
        vector_hits,
        vacancies_by_id,
    ):
        resume = SimpleNamespace(
            analysis={
                "target_role": "Senior Backend Engineer",
                "hard_skills": ["python", "postgres", "docker"],
                "matching_keywords": ["backend", "python"],
            }
        )
        vector_store = MagicMock()
        vector_store.get_resume_vector.return_value = [0.1] * 8
        vector_store.get_user_preference_vectors.return_value = (None, None)
        vector_store.search_vacancy_profiles.return_value = vector_hits

        db = MagicMock()
        db.get.return_value = user
        patchers = [
            patch("app.services.matching_service.get_resume_for_user", return_value=resume),
            patch("app.services.matching_service.get_vector_store", return_value=vector_store),
            patch(
                "app.services.matching_service.recompute_user_preference_profile",
                return_value=None,
            ),
            patch("app.services.matching_service.list_disliked_vacancy_ids", return_value=[]),
            patch("app.services.matching_service.list_liked_vacancy_ids", return_value=[]),
            patch(
                "app.services.matching_service.get_vacancy_by_id",
                side_effect=lambda _db, vacancy_id: vacancies_by_id.get(vacancy_id),
            ),
            patch("app.services.matching_service._host_allowed_for_matching", return_value=True),
            patch("app.services.matching_service._looks_non_vacancy_page", return_value=False),
            patch(
                "app.services.matching_service._looks_archived_vacancy_strict",
                return_value=False,
            ),
            patch("app.services.matching_service._looks_like_listing_page", return_value=False),
            patch("app.services.matching_service._looks_unlikely_stack", return_value=False),
            patch(
                "app.services.matching_service._looks_business_monitoring_role",
                return_value=False,
            ),
            patch("app.services.matching_service._looks_hard_non_it_role", return_value=False),
            patch("app.services.matching_service._lexical_fallback_matches", return_value=[]),
        ]
        return db, patchers

    def _vacancy(self, vacancy_id: int, title: str, location: str, remote_policy: str):
        return SimpleNamespace(
            id=vacancy_id,
            status="indexed",
            source="hh_api",
            source_url=f"https://hh.ru/vacancy/{vacancy_id}",
            title=title,
            company=f"Co{vacancy_id}",
            location=location,
            raw_text="python postgres",
        ), {
            "vacancy_id": vacancy_id,
            "is_vacancy": True,
            "title": title,
            "remote_policy": remote_policy,
            "location": location,
            "matching_keywords": ["python", "backend"],
            "must_have_skills": ["python"],
            "summary": "Python backend role",
        }

    def test_work_format_drop_counted_and_excluded(self) -> None:
        v_remote, p_remote = self._vacancy(101, "Senior Backend Engineer", "Remote", "remote")
        v_office, p_office = self._vacancy(102, "Backend Developer", "Москва", "office")
        vector_hits = [(101, 0.85, p_remote), (102, 0.80, p_office)]
        vacancies_by_id = {101: v_remote, 102: v_office}
        user = SimpleNamespace(
            preferred_work_format="remote",
            relocation_mode="any_city",
            home_city=None,
            preferred_titles=[],
        )
        db, patchers = self._make_context(
            user=user, vector_hits=vector_hits, vacancies_by_id=vacancies_by_id
        )
        metrics: dict = {}
        with (
            patchers[0],
            patchers[1],
            patchers[2],
            patchers[3],
            patchers[4],
            patchers[5],
            patchers[6],
            patchers[7],
            patchers[8],
            patchers[9],
            patchers[10],
            patchers[11],
            patchers[12],
            patchers[13],
        ):
            matches = match_vacancies_for_resume(
                db, resume_id=1, user_id=7, limit=20, metrics=metrics
            )

        self.assertEqual([m["vacancy_id"] for m in matches], [101])
        self.assertEqual(metrics["hard_filter_drop_work_format"], 1)
        self.assertEqual(metrics["hard_filter_drop_geo"], 0)

    def test_geo_drop_counted_and_remote_bypasses_geo(self) -> None:
        v_spb, p_spb = self._vacancy(201, "Senior Backend Engineer", "Санкт-Петербург", "office")
        v_remote, p_remote = self._vacancy(202, "Backend Developer", "Санкт-Петербург", "remote")
        v_msk, p_msk = self._vacancy(203, "Backend Developer", "Москва", "office")
        vector_hits = [
            (201, 0.85, p_spb),
            (202, 0.80, p_remote),
            (203, 0.82, p_msk),
        ]
        vacancies_by_id = {201: v_spb, 202: v_remote, 203: v_msk}
        user = SimpleNamespace(
            preferred_work_format="any",
            relocation_mode="home_only",
            home_city="Москва",
            preferred_titles=[],
        )
        db, patchers = self._make_context(
            user=user, vector_hits=vector_hits, vacancies_by_id=vacancies_by_id
        )
        metrics: dict = {}
        with (
            patchers[0],
            patchers[1],
            patchers[2],
            patchers[3],
            patchers[4],
            patchers[5],
            patchers[6],
            patchers[7],
            patchers[8],
            patchers[9],
            patchers[10],
            patchers[11],
            patchers[12],
            patchers[13],
        ):
            matches = match_vacancies_for_resume(
                db, resume_id=1, user_id=7, limit=20, metrics=metrics
            )

        ids = {m["vacancy_id"] for m in matches}
        self.assertIn(202, ids)
        self.assertIn(203, ids)
        self.assertNotIn(201, ids)
        self.assertEqual(metrics["hard_filter_drop_geo"], 1)

    def test_title_boost_lifts_score(self) -> None:
        v_a, p_a = self._vacancy(301, "Senior Backend Engineer", "Remote", "remote")
        v_b, p_b = self._vacancy(302, "Python Developer", "Remote", "remote")
        vector_hits = [(301, 0.68, p_a), (302, 0.68, p_b)]
        vacancies_by_id = {301: v_a, 302: v_b}
        user_no_titles = SimpleNamespace(
            preferred_work_format="any",
            relocation_mode="any_city",
            home_city=None,
            preferred_titles=[],
        )
        db, patchers = self._make_context(
            user=user_no_titles, vector_hits=vector_hits, vacancies_by_id=vacancies_by_id
        )
        with (
            patchers[0],
            patchers[1],
            patchers[2],
            patchers[3],
            patchers[4],
            patchers[5],
            patchers[6],
            patchers[7],
            patchers[8],
            patchers[9],
            patchers[10],
            patchers[11],
            patchers[12],
            patchers[13],
        ):
            baseline = match_vacancies_for_resume(db, resume_id=1, user_id=7, limit=20)
        baseline_301 = next(m for m in baseline if m["vacancy_id"] == 301)

        user_with_titles = SimpleNamespace(
            preferred_work_format="any",
            relocation_mode="any_city",
            home_city=None,
            preferred_titles=["Senior Backend Engineer"],
        )
        db2, patchers2 = self._make_context(
            user=user_with_titles, vector_hits=vector_hits, vacancies_by_id=vacancies_by_id
        )
        metrics: dict = {}
        with (
            patchers2[0],
            patchers2[1],
            patchers2[2],
            patchers2[3],
            patchers2[4],
            patchers2[5],
            patchers2[6],
            patchers2[7],
            patchers2[8],
            patchers2[9],
            patchers2[10],
            patchers2[11],
            patchers2[12],
            patchers2[13],
        ):
            boosted = match_vacancies_for_resume(
                db2, resume_id=1, user_id=7, limit=20, metrics=metrics
            )
        boosted_301 = next(m for m in boosted if m["vacancy_id"] == 301)
        boosted_302 = next(m for m in boosted if m["vacancy_id"] == 302)

        # Vacancy 301 got the boost; 302 didn't.
        self.assertAlmostEqual(
            boosted_301["similarity_score"],
            round(baseline_301["similarity_score"] + 0.10, 5),
            places=4,
        )
        self.assertAlmostEqual(
            boosted_302["similarity_score"],
            next(m for m in baseline if m["vacancy_id"] == 302)["similarity_score"],
            places=4,
        )
        self.assertEqual(metrics["title_boost_applied"], 1)

    def test_per_request_override_disables_format_filter(self) -> None:
        v_office, p_office = self._vacancy(401, "Backend Developer", "Москва", "office")
        vector_hits = [(401, 0.80, p_office)]
        vacancies_by_id = {401: v_office}
        user = SimpleNamespace(
            preferred_work_format="remote",
            relocation_mode="any_city",
            home_city=None,
            preferred_titles=[],
        )
        db, patchers = self._make_context(
            user=user, vector_hits=vector_hits, vacancies_by_id=vacancies_by_id
        )
        with (
            patchers[0],
            patchers[1],
            patchers[2],
            patchers[3],
            patchers[4],
            patchers[5],
            patchers[6],
            patchers[7],
            patchers[8],
            patchers[9],
            patchers[10],
            patchers[11],
            patchers[12],
            patchers[13],
        ):
            matches = match_vacancies_for_resume(
                db,
                resume_id=1,
                user_id=7,
                limit=20,
                preference_overrides={"preferred_work_format": "any"},
            )
        self.assertEqual([m["vacancy_id"] for m in matches], [401])


if __name__ == "__main__":
    unittest.main()
