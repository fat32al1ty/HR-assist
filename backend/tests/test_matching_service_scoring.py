import unittest

from app.services.matching_service import (
    FALLBACK_MIN_RELEVANCE_SCORE,
    LEADERSHIP_HINT_TOKENS,
    MIN_RELEVANCE_SCORE,
    _augment_profile_with_gap_insights,
    _extract_priority_anchors,
    _extract_resume_hard_skills,
    _extract_strict_technical_anchors,
    _extract_technical_anchors,
    _hybrid_score,
    _looks_business_monitoring_role,
    _looks_hard_non_it_role,
    _matched_resume_skills_for_vacancy,
    _phrase_aliases,
    _resume_prefers_leadership,
    _title_has_leadership_hint,
    _tokenize_text,
)


class MatchingServiceScoringTests(unittest.TestCase):
    def test_tokenize_text_normalizes_punctuation_and_slashes(self) -> None:
        tokens = _tokenize_text("Head of monitoring / Observability, Platform-services")
        self.assertIn("observability", tokens)
        self.assertIn("monitoring", tokens)
        self.assertIn("platform", tokens)
        self.assertIn("services", tokens)
        self.assertNotIn("observability,", tokens)

    def test_hybrid_score_keeps_strong_vector_signal(self) -> None:
        score = _hybrid_score(0.62, 0.08)
        self.assertGreaterEqual(score, FALLBACK_MIN_RELEVANCE_SCORE)
        self.assertGreaterEqual(score, MIN_RELEVANCE_SCORE)

    def test_leadership_preference_detection(self) -> None:
        self.assertIn("head", LEADERSHIP_HINT_TOKENS)
        self.assertTrue(_resume_prefers_leadership({"head", "monitoring"}))
        self.assertFalse(_resume_prefers_leadership({"devops", "monitoring"}))

    def test_title_leadership_hint_detection(self) -> None:
        self.assertTrue(_title_has_leadership_hint("Team Lead DevOps"))
        self.assertTrue(_title_has_leadership_hint("Engineer", {"seniority": "Lead"}))
        self.assertFalse(_title_has_leadership_hint("DevOps Engineer"))

    def test_priority_anchor_extraction(self) -> None:
        anchors = _extract_priority_anchors(
            {
                "target_role": "Head of Monitoring / Observability",
                "specialization": "Platform services",
                "matching_keywords": ["monitoring", "platform"],
                "hard_skills": ["Prometheus"],
            }
        )
        self.assertIn("observability", anchors)
        self.assertIn("monitoring", anchors)

    def test_technical_anchor_extraction(self) -> None:
        anchors = _extract_technical_anchors(
            {"prometheus", "grafana", "vendor management"},
            {"target_role": "Head of observability", "specialization": "platform services"},
        )
        self.assertIn("prometheus", anchors)
        self.assertIn("grafana", anchors)
        self.assertIn("observability", anchors)

    def test_strict_technical_anchor_extraction(self) -> None:
        anchors = _extract_strict_technical_anchors({"prometheus", "grafana", "vendor management"})
        self.assertIn("prometheus", anchors)
        self.assertIn("grafana", anchors)
        self.assertNotIn("vendor management", anchors)

    def test_business_monitoring_role_is_filtered_for_technical_profile(self) -> None:
        self.assertTrue(_looks_business_monitoring_role("Head of financial monitoring", {"prometheus", "grafana"}))
        self.assertFalse(_looks_business_monitoring_role("Head of SRE team", {"prometheus", "grafana"}))

    def test_hard_non_it_role_filter_blocks_chemistry_roles(self) -> None:
        self.assertTrue(
            _looks_hard_non_it_role(
                "Руководитель лаборатории, Химик",
                {"domains": ["Химическая лаборатория"]},
                "Проведение химических анализов и оформление протоколов",
            )
        )
        self.assertFalse(
            _looks_hard_non_it_role(
                "Team Lead SRE",
                {"domains": ["Observability", "Platform engineering"]},
                "Monitoring platform and incident management",
            )
        )

    def test_gap_insights_returns_missing_requirements(self) -> None:
        payload = {
            "must_have_skills": ["Kubernetes", "Prometheus", "Grafana"],
            "tools": ["VictoriaMetrics"],
        }
        profile = _augment_profile_with_gap_insights(
            payload,
            {"prometheus", "linux"},
            resume_skill_phrases=["SRE", "Linux", "Incident response"],
            resume_phrase_aliases=_phrase_aliases("SRE").union(_phrase_aliases("Linux")).union(_phrase_aliases("Incident response")),
            resume_phrase_vectors={},
            embedding_cache={},
            embedding_budget={"calls_left": 0},
        )
        self.assertIn("Kubernetes", profile["missing_requirements"])
        self.assertIn("Grafana", profile["missing_requirements"])
        self.assertIn("VictoriaMetrics", profile["missing_requirements"])
        self.assertEqual(profile["missing_requirements_count"], 3)
        self.assertEqual(profile["required_requirements_count"], 4)

    def test_gap_insights_aliases_but_keeps_devops_strict(self) -> None:
        payload = {
            "must_have_skills": ["DevOps", "team lead", "incident-management"],
            "tools": [],
        }
        profile = _augment_profile_with_gap_insights(
            payload,
            {"sre", "leadership", "incident"},
            resume_skill_phrases=["SRE", "team leadership", "incident response"],
            resume_phrase_aliases=_phrase_aliases("SRE").union(_phrase_aliases("team leadership")).union(_phrase_aliases("incident response")),
            resume_phrase_vectors={},
            embedding_cache={},
            embedding_budget={"calls_left": 0},
        )
        self.assertEqual(profile["missing_requirements"], ["DevOps"])

    def test_leadership_requirement_matches_management_phrases(self) -> None:
        payload = {
            "must_have_skills": ["team management", "task prioritization", "capacity planning"],
            "tools": [],
        }
        profile = _augment_profile_with_gap_insights(
            payload,
            {"leadership", "management", "prioritization", "planning"},
            resume_skill_phrases=[
                "Managed cross-functional teams",
                "Prioritized team backlog and tasks",
                "Capacity planning for engineering team",
            ],
            resume_phrase_aliases=_phrase_aliases("Managed cross-functional teams")
            .union(_phrase_aliases("Prioritized team backlog and tasks"))
            .union(_phrase_aliases("Capacity planning for engineering team")),
            resume_phrase_vectors={},
            embedding_cache={},
            embedding_budget={"calls_left": 0},
        )
        self.assertEqual(profile["missing_requirements_count"], 0)

    def test_gap_insights_surfaces_matched_requirements_and_skills(self) -> None:
        payload = {
            "must_have_skills": ["Kubernetes", "Prometheus", "Grafana"],
            "tools": ["VictoriaMetrics"],
        }
        profile = _augment_profile_with_gap_insights(
            payload,
            {"prometheus", "linux", "kubernetes"},
            resume_hard_skills=["Prometheus", "K8s", "Linux"],
            resume_skill_phrases=["SRE", "Linux", "Kubernetes"],
            resume_phrase_aliases=_phrase_aliases("SRE")
            .union(_phrase_aliases("Linux"))
            .union(_phrase_aliases("Kubernetes")),
            resume_phrase_vectors={},
            embedding_cache={},
            embedding_budget={"calls_left": 0},
        )
        # Kubernetes + Prometheus are in the resume; Grafana + VictoriaMetrics are not.
        self.assertIn("Prometheus", profile["matched_requirements"])
        self.assertIn("Kubernetes", profile["matched_requirements"])
        self.assertIn("Grafana", profile["missing_requirements"])
        self.assertIn("VictoriaMetrics", profile["missing_requirements"])
        # Resume-side: original casing preserved, k8s alias hits vacancy's kubernetes.
        self.assertIn("Prometheus", profile["matched_skills"])
        self.assertIn("K8s", profile["matched_skills"])
        # "Linux" was in resume but vacancy didn't ask for it — must NOT appear.
        self.assertNotIn("Linux", profile["matched_skills"])

    def test_matched_resume_skills_caps_and_dedupes(self) -> None:
        # Vacancy uses "kubernetes"; resume has both spellings — only one wins.
        tokens = {"kubernetes", "prometheus"}
        matched = _matched_resume_skills_for_vacancy(
            ["Kubernetes", "kubernetes", "Prometheus", "Grafana"],
            tokens,
            max_items=10,
        )
        self.assertEqual(matched.count("Kubernetes") + matched.count("kubernetes"), 1)
        self.assertIn("Prometheus", matched)
        self.assertNotIn("Grafana", matched)

    def test_extract_resume_hard_skills_preserves_casing_and_dedupes(self) -> None:
        skills = _extract_resume_hard_skills(
            {
                "hard_skills": ["Kubernetes", "Prometheus"],
                "tools": ["kubernetes", "Grafana"],
                "matching_keywords": ["SRE"],
            }
        )
        self.assertEqual(skills[0], "Kubernetes")
        self.assertIn("Prometheus", skills)
        self.assertIn("Grafana", skills)
        self.assertIn("SRE", skills)
        # "kubernetes" in tools duplicates "Kubernetes" — must be deduped.
        self.assertEqual(skills.count("Kubernetes"), 1)
        lowercased = [s.lower() for s in skills]
        self.assertEqual(lowercased.count("kubernetes"), 1)

    def test_capacity_requirement_matches_planning_signals(self) -> None:
        payload = {
            "must_have_skills": ["планирование загрузки"],
            "tools": [],
        }
        profile = _augment_profile_with_gap_insights(
            payload,
            {"planning", "prioritization", "команда", "delivery"},
            resume_skill_phrases=[
                "Strategic planning",
                "Task prioritization",
                "Managed delivery for engineering team",
            ],
            resume_phrase_aliases=_phrase_aliases("Strategic planning")
            .union(_phrase_aliases("Task prioritization"))
            .union(_phrase_aliases("Managed delivery for engineering team")),
            resume_phrase_vectors={},
            embedding_cache={},
            embedding_budget={"calls_left": 0},
        )
        self.assertEqual(profile["missing_requirements"], [])


if __name__ == "__main__":
    unittest.main()
