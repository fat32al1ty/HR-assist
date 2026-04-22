import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.matching_service import (
    DOMAIN_MISMATCH_PENALTY,
    match_vacancies_for_resume,
)


def _make_vacancy(vid: int, title: str = "Hardware ML Engineer") -> SimpleNamespace:
    return SimpleNamespace(
        id=vid,
        status="indexed",
        source="hh_api",
        source_url=f"https://hh.ru/vacancy/{vid}",
        title=title,
        company="Acme",
        location="Moscow",
        raw_text="embedded hardware ml automotive",
    )


class DomainSoftPenaltyTest(unittest.TestCase):
    """Phase 2.0 PR B2 — domain mismatch used to drop items outright,
    hiding senior cross-domain candidates like ML-on-hardware. Now the
    gate subtracts DOMAIN_MISMATCH_PENALTY from the hybrid score so the
    item only surfaces when everything else is strong.
    """

    def _run_match(
        self,
        *,
        resume_domains: list[str],
        vacancy_domains: list[str],
        semantic_score: float,
    ) -> list[dict]:
        resume = SimpleNamespace(
            analysis={
                "target_role": "ML Platform Engineer",
                "specialization": "Machine Learning",
                "hard_skills": ["python", "pytorch"],
                "matching_keywords": ["ml", "platform"],
                "domains": resume_domains,
            }
        )
        profile = {
            "vacancy_id": 42,
            "is_vacancy": True,
            "title": "Hardware ML Engineer",
            "matching_keywords": ["ml", "hardware"],
            "must_have_skills": ["python"],
            "summary": "hardware ml engineer",
            "domains": vacancy_domains,
        }
        vector_store = MagicMock()
        vector_store.get_resume_vector.return_value = [0.1] * 10
        vector_store.get_user_preference_vectors.return_value = (None, None)
        vector_store.search_vacancy_profiles.return_value = [(42, semantic_score, profile)]

        def _get_vacancy(_db, vacancy_id):
            return _make_vacancy(vacancy_id)

        with (
            patch("app.services.matching_service.get_resume_for_user", return_value=resume),
            patch("app.services.matching_service.get_vector_store", return_value=vector_store),
            patch(
                "app.services.matching_service.recompute_user_preference_profile",
                return_value=None,
            ),
            patch("app.services.matching_service.list_disliked_vacancy_ids", return_value=[]),
            patch("app.services.matching_service.list_liked_vacancy_ids", return_value=[]),
            patch("app.services.matching_service.list_added_skill_texts", return_value=[]),
            patch("app.services.matching_service.list_rejected_skill_texts", return_value=[]),
            patch("app.services.matching_service.get_vacancy_by_id", side_effect=_get_vacancy),
            patch("app.services.matching_service._host_allowed_for_matching", return_value=True),
            patch("app.services.matching_service._looks_non_vacancy_page", return_value=False),
            patch(
                "app.services.matching_service._looks_archived_vacancy_strict", return_value=False
            ),
            patch("app.services.matching_service._looks_like_listing_page", return_value=False),
            patch("app.services.matching_service._looks_unlikely_stack", return_value=False),
            patch("app.services.matching_service._lexical_fallback_matches", return_value=[]),
        ):
            return match_vacancies_for_resume(SimpleNamespace(), resume_id=1, user_id=1, limit=10)

    def test_cross_domain_item_is_returned_with_penalty_applied(self) -> None:
        # Resume is IT, vacancy is hardware. Old behavior: drop. New behavior:
        # keep at reduced score.
        matches = self._run_match(
            resume_domains=["Platform Services", "SRE", "Observability"],
            vacancy_domains=["Автомобилестроение", "Электронные системы автомобиля"],
            semantic_score=0.95,
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["vacancy_id"], 42)

    def test_matching_domain_item_is_not_penalized(self) -> None:
        # Both sides IT → no penalty, score stays high.
        matches = self._run_match(
            resume_domains=["Platform Services", "SRE"],
            vacancy_domains=["SRE", "DevOps", "Cloud"],
            semantic_score=0.95,
        )

        self.assertEqual(len(matches), 1)
        non_penalized = matches[0]["similarity_score"]

        # Same semantic score, but cross-domain → penalty applied.
        cross = self._run_match(
            resume_domains=["Platform Services", "SRE"],
            vacancy_domains=["Автомобилестроение"],
            semantic_score=0.95,
        )
        self.assertEqual(len(cross), 1)
        penalized = cross[0]["similarity_score"]

        # Penalty must be observable in the score (within 1e-4 of the delta).
        self.assertAlmostEqual(non_penalized - penalized, DOMAIN_MISMATCH_PENALTY, places=4)

    def test_low_score_cross_domain_still_reaches_maybe_tier(self) -> None:
        # A mid-score cross-domain item (semantic 0.70) should land in the
        # "maybe" bucket after the penalty; previously it was dropped.
        matches = self._run_match(
            resume_domains=["SRE", "DevOps"],
            vacancy_domains=["Юридическая практика"],
            semantic_score=0.70,
        )
        self.assertEqual(len(matches), 1)
        self.assertIn(matches[0]["tier"], {"strong", "maybe"})


if __name__ == "__main__":
    unittest.main()
