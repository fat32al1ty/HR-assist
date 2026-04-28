"""Unit tests for _build_discovery_query with preferred_titles / preferred_domains.

T12: preferred_titles=["Tech Lead"] → "Tech Lead" (normalized) appears in the query.
T13: preferred_domains=["FinTech"] → "FinTech" (normalized) appears in the query.
T14: preferred_titles=None, preferred_domains=None → falls back to analysis-derived
     tokens (regression guard for existing behaviour).
"""

from __future__ import annotations

import unittest

from app.services.vacancy_recommendation import _build_discovery_query


class BuildDiscoveryQueryPrefsTest(unittest.TestCase):
    _BASE_ANALYSIS = {
        "target_role": "Software Engineer",
        "specialization": "Python",
        "hard_skills": ["Python", "FastAPI"],
        "matching_keywords": ["backend", "api"],
    }

    # T12 ────────────────────────────────────────────────────────────────────
    def test_preferred_titles_override_appears_in_query(self) -> None:
        """When preferred_titles=["Tech Lead"], "tech lead" should be in the result."""
        query = _build_discovery_query(
            self._BASE_ANALYSIS,
            preferred_titles=["Tech Lead"],
            preferred_domains=[],
        )
        self.assertIn("tech lead", query.lower())

    # T13 ────────────────────────────────────────────────────────────────────
    def test_preferred_domains_appear_in_query(self) -> None:
        """When preferred_domains=["FinTech"], "fintech" should be in the result."""
        query = _build_discovery_query(
            self._BASE_ANALYSIS,
            preferred_titles=[],
            preferred_domains=["FinTech"],
        )
        self.assertIn("fintech", query.lower())

    # T14 ────────────────────────────────────────────────────────────────────
    def test_none_prefs_falls_back_to_analysis(self) -> None:
        """Both prefs=None → query derived from analysis target_role / specialization."""
        query = _build_discovery_query(
            self._BASE_ANALYSIS,
            preferred_titles=None,
            preferred_domains=None,
        )
        # The analysis has "Software Engineer" as target_role; at least one
        # meaningful token from it should appear.
        self.assertTrue(
            "software" in query.lower() or "engineer" in query.lower(),
            f"Expected analysis-derived role token in query, got: {query!r}",
        )

    def test_empty_analysis_with_titles_override(self) -> None:
        """Even with no analysis, preferred_titles drives the query."""
        query = _build_discovery_query(
            None,
            preferred_titles=["Data Engineer"],
            preferred_domains=[],
        )
        self.assertIn("data", query.lower())

    def test_empty_analysis_with_domains_only_returns_nonempty_query(self) -> None:
        """Domains alone (no analysis, no titles) still produce a non-empty query."""
        query = _build_discovery_query(
            None,
            preferred_titles=[],
            preferred_domains=["EdTech"],
        )
        # Either "edtech" is present, or the fallback default kicks in.
        self.assertTrue(len(query.strip()) > 0)


if __name__ == "__main__":
    unittest.main()
