"""Integration tests for the domain-preference soft-boost in ScoringStage.

T15: User with preferred_domains=["FinTech"].
     - FinTech vacancy gets +0.03 over the no-preference baseline.
     - HealthTech vacancy score is unchanged vs baseline.
     - NEITHER vacancy is dropped.
     - domain_preference_boost_applied == 1 in the metrics dict.

T16: preferred_domains=[] → boost is never applied; domain_preference_boost_applied == 0;
     scores identical to baseline.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.matching_service import (
    DOMAIN_PREFERENCE_BOOST,
    match_vacancies_for_resume,
)

# IT domains: both vacancies fall inside the "soft" compatibility zone so the
# domain-mismatch penalty (DOMAIN_MISMATCH_PENALTY) is NOT triggered by either.
# This keeps the comparison clean — we're only measuring the boost delta.
_RESUME_IT_DOMAINS = ["Backend", "Platform Engineering"]
_FINTECH_VACANCY_DOMAINS = ["FinTech", "Banking"]
_HEALTHTECH_VACANCY_DOMAINS = ["HealthTech", "MedTech"]

_SEMANTIC_SCORE = 0.80  # above the hard-drop floor, below seniority noise

_RESUME_ANALYSIS = {
    "target_role": "Backend Engineer",
    "specialization": "Python",
    "hard_skills": ["Python", "FastAPI"],
    "matching_keywords": ["backend", "api"],
    "domains": _RESUME_IT_DOMAINS,
}

_FT_VACANCY_ID = 101
_HT_VACANCY_ID = 102


def _make_vacancy(vid: int, title: str = "Software Engineer") -> SimpleNamespace:
    return SimpleNamespace(
        id=vid,
        status="indexed",
        source="hh_api",
        source_url=f"https://hh.ru/vacancy/{vid}",
        title=title,
        company="TestCo",
        location="Moscow",
        raw_text="backend engineer python api",
    )


def _make_profile(domains: list[str]) -> dict:
    return {
        "vacancy_id": 999,  # overwritten by the stub
        "is_vacancy": True,
        "title": "Software Engineer",
        "matching_keywords": ["backend", "python"],
        "must_have_skills": ["python"],
        "summary": "backend api engineer",
        "domains": domains,
    }


def _run_match(*, preferred_domains: list[str]) -> tuple[list[dict], dict]:
    """Return (matches, metrics_dict) for a 2-vacancy search.

    preferred_domains is injected via preference_overrides so the test never
    needs to touch the database User row.
    """
    ft_profile = _make_profile(_FINTECH_VACANCY_DOMAINS)
    ht_profile = _make_profile(_HEALTHTECH_VACANCY_DOMAINS)

    vector_store = MagicMock()
    vector_store.get_resume_vector.return_value = [0.1] * 10
    vector_store.get_user_preference_vectors.return_value = (None, None)
    vector_store.search_vacancy_profiles.return_value = [
        (_FT_VACANCY_ID, _SEMANTIC_SCORE, ft_profile),
        (_HT_VACANCY_ID, _SEMANTIC_SCORE, ht_profile),
    ]

    vacancies_map = {
        _FT_VACANCY_ID: _make_vacancy(_FT_VACANCY_ID, "FinTech Backend Engineer"),
        _HT_VACANCY_ID: _make_vacancy(_HT_VACANCY_ID, "HealthTech Platform Engineer"),
    }

    def _get_vacancy(_db, vacancy_id):
        return vacancies_map[vacancy_id]

    resume = SimpleNamespace(analysis=_RESUME_ANALYSIS)
    metrics: dict = {}

    with (
        patch("app.services.matching_service.get_resume_for_user", return_value=resume),
        patch("app.services.matching_service.get_vector_store", return_value=vector_store),
        patch("app.services.matching_service.recompute_user_preference_profile", return_value=None),
        patch("app.services.matching_service.list_applied_vacancy_ids_for_user", return_value=[]),
        patch("app.services.matching_service.list_disliked_vacancy_ids", return_value=[]),
        patch("app.services.matching_service.list_liked_vacancy_ids", return_value=[]),
        patch(
            "app.services.matching_service.list_seen_vacancy_ids_from_feedback", return_value=set()
        ),
        patch("app.services.matching_service.list_seen_vacancy_ids", return_value=set()),
        patch("app.services.matching_service.list_added_skill_texts", return_value=[]),
        patch("app.services.matching_service.list_rejected_skill_texts", return_value=[]),
        patch("app.services.matching_service.get_vacancy_by_id", side_effect=_get_vacancy),
        patch("app.services.matching_service._host_allowed_for_matching", return_value=True),
        patch("app.services.matching_service._looks_non_vacancy_page", return_value=False),
        patch("app.services.matching_service._looks_archived_vacancy_strict", return_value=False),
        patch("app.services.matching_service._looks_like_listing_page", return_value=False),
        patch("app.services.matching_service._looks_unlikely_stack", return_value=False),
        patch("app.services.matching_service._lexical_fallback_matches", return_value=[]),
    ):
        overrides = {"preferred_domains": preferred_domains} if preferred_domains is not None else None
        matches = match_vacancies_for_resume(
            SimpleNamespace(),
            resume_id=1,
            user_id=1,
            limit=20,
            preference_overrides=overrides,
            metrics=metrics,
        )

    return matches, metrics


class DomainPreferenceBoostTest(unittest.TestCase):
    # T15 ────────────────────────────────────────────────────────────────────
    def test_fintech_vacancy_gets_boost_healthtech_does_not(self) -> None:
        """preferred_domains=["FinTech"]:
        - FinTech vacancy score is exactly DOMAIN_PREFERENCE_BOOST (0.03) above baseline.
        - HealthTech vacancy score is unchanged.
        - Neither vacancy is dropped.
        - domain_preference_boost_applied == 1.
        """
        # Baseline: no domain preference.
        baseline_matches, _ = _run_match(preferred_domains=[])
        self.assertEqual(len(baseline_matches), 2, "Both vacancies must survive baseline run")

        baseline = {m["vacancy_id"]: m["similarity_score"] for m in baseline_matches}

        # With FinTech preference.
        boosted_matches, metrics = _run_match(preferred_domains=["FinTech"])
        self.assertEqual(
            len(boosted_matches), 2, "Both vacancies must survive preference run (no drops)"
        )

        boosted = {m["vacancy_id"]: m["similarity_score"] for m in boosted_matches}

        ft_delta = boosted[_FT_VACANCY_ID] - baseline[_FT_VACANCY_ID]
        ht_delta = boosted[_HT_VACANCY_ID] - baseline[_HT_VACANCY_ID]

        self.assertAlmostEqual(
            ft_delta,
            DOMAIN_PREFERENCE_BOOST,
            places=4,
            msg=(
                f"FinTech vacancy should gain exactly +{DOMAIN_PREFERENCE_BOOST}, "
                f"got delta {ft_delta:.5f}"
            ),
        )
        self.assertAlmostEqual(
            ht_delta,
            0.0,
            places=4,
            msg=(
                f"HealthTech vacancy score must not change, "
                f"got delta {ht_delta:.5f}"
            ),
        )

        self.assertEqual(
            metrics.get("domain_preference_boost_applied", 0),
            1,
            f"Expected domain_preference_boost_applied=1, got {metrics}",
        )

    # T16 ────────────────────────────────────────────────────────────────────
    def test_empty_preferred_domains_no_boost_applied(self) -> None:
        """preferred_domains=[] → domain_preference_boost_applied == 0; scores identical to baseline."""
        baseline_matches, _ = _run_match(preferred_domains=[])
        empty_matches, metrics = _run_match(preferred_domains=[])

        self.assertEqual(len(baseline_matches), 2)
        self.assertEqual(len(empty_matches), 2)

        baseline = {m["vacancy_id"]: m["similarity_score"] for m in baseline_matches}
        empty = {m["vacancy_id"]: m["similarity_score"] for m in empty_matches}

        for vid in (_FT_VACANCY_ID, _HT_VACANCY_ID):
            self.assertAlmostEqual(
                baseline[vid],
                empty[vid],
                places=5,
                msg=f"Scores must be identical with no domain preference for vacancy {vid}",
            )

        self.assertEqual(
            metrics.get("domain_preference_boost_applied", 0),
            0,
            f"Expected domain_preference_boost_applied=0, got {metrics}",
        )


if __name__ == "__main__":
    unittest.main()
