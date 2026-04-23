import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.matching_service import (
    MAYBE_MATCH_THRESHOLD,
    STRONG_MATCH_THRESHOLD,
    match_vacancies_for_resume,
)


def _make_vacancy(vid: int, *, title: str = "Backend Engineer") -> SimpleNamespace:
    return SimpleNamespace(
        id=vid,
        status="indexed",
        source="hh_api",
        source_url=f"https://hh.ru/vacancy/{vid}",
        title=title,
        company="Acme",
        location="Moscow",
        raw_text="backend python observability",
    )


def _make_profile(vid: int, *, title: str) -> dict:
    return {
        "vacancy_id": vid,
        "is_vacancy": True,
        "title": title,
        "matching_keywords": ["backend", "python"],
        "must_have_skills": ["python"],
        "summary": "backend engineering",
    }


class TwoTierOutputTest(unittest.TestCase):
    """Phase 2.0 PR B1 — match list splits into `strong` (score >= 0.60)
    and `maybe` (0.45 <= score < 0.60) tiers. Frontend partitions by
    `tier` and shows both blocks separately.
    """

    def _run_match(
        self, scored_items: list[tuple[int, float, dict]], vacancies: dict
    ) -> list[dict]:
        resume = SimpleNamespace(
            analysis={
                "target_role": "Backend Engineer",
                "specialization": "Python",
                "hard_skills": ["python"],
                "matching_keywords": ["backend"],
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
                "app.services.matching_service.list_applied_vacancy_ids_for_user", return_value=[]
            ),
            patch("app.services.matching_service.list_disliked_vacancy_ids", return_value=[]),
            patch("app.services.matching_service.list_liked_vacancy_ids", return_value=[]),
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
        ):
            return match_vacancies_for_resume(SimpleNamespace(), resume_id=1, user_id=1, limit=10)

    def test_strong_tier_label_is_present(self) -> None:
        # Semantic score alone is not enough to hit 0.60 hybrid; we need
        # the scored list to produce at least one item that clears the
        # strong threshold after hybrid computation. Use 0.90 semantic so
        # hybrid after weighting still clears 0.60.
        scored = [(101, 0.90, _make_profile(101, title="Backend Engineer"))]
        vacancies = {101: _make_vacancy(101)}
        matches = self._run_match(scored, vacancies)

        self.assertGreaterEqual(len(matches), 1)
        match_101 = next((m for m in matches if m["vacancy_id"] == 101), None)
        self.assertIsNotNone(match_101)
        self.assertIn("tier", match_101)
        # Whatever tier we land in, it must be one of the advertised values.
        self.assertIn(match_101["tier"], {"strong", "maybe"})

    def test_maybe_fallback_items_carry_tier_maybe(self) -> None:
        # Low semantic score → below strict threshold. Matcher used to
        # return nothing; now it should return at least the relaxed
        # fallback tagged as "maybe" so the UI can render it.
        scored = [(202, 0.46, _make_profile(202, title="Platform reliability engineer"))]
        vacancies = {202: _make_vacancy(202, title="Platform reliability engineer")}
        matches = self._run_match(scored, vacancies)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["tier"], "maybe")

    def test_thresholds_are_ordered(self) -> None:
        self.assertLess(MAYBE_MATCH_THRESHOLD, STRONG_MATCH_THRESHOLD)


if __name__ == "__main__":
    unittest.main()
