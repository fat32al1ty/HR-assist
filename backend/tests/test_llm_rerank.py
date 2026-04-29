"""Phase 2.5b — LLMRerankStage unit tests.

Exercises the stage without hitting OpenAI or the disk cache: the
``OpenAI`` client is patched out, and ``rerank_cache`` read/write are
monkey-patched so cache-hit and cache-miss paths are both covered.

Scenarios:
  * flag-off and missing API key → no-op
  * cache hit → reorder + annotate, no LLM call
  * cache miss → call LLM, annotate + nudge hybrid, cache the result
  * LLM failure → fallback annotations, no crash
  * budget exhausted → skip with ``rerank_skipped`` annotation
  * ``_splice_head`` preserves dropped candidates and tail beyond head
  * requirements_check shape validation
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from app.core.config import settings
from app.services.matching.stages import llm_rerank
from app.services.matching.stages.llm_rerank import LLMRerankStage
from app.services.matching.state import (
    Candidate,
    MatchingDiagnostics,
    MatchingState,
    ResumeContext,
)


def _ctx() -> ResumeContext:
    return ResumeContext(
        resume_id=42,
        user_id=7,
        analysis={
            "target_role": "backend engineer",
            "specialization": "platform",
            "seniority": "senior",
            "role_family": "software_engineering",
            "home_city": "Moscow",
            "total_years": 5,
        },
        query_vector=[0.0],
        resume_skills=set(),
        resume_roles=set(),
        resume_skill_phrases=[],
        resume_hard_skills=["python", "kafka", "kubernetes"],
        resume_phrase_aliases=set(),
        resume_total_years=None,
        leadership_preferred=False,
        preferences={},
        preferred_titles=[],
        excluded_vacancy_ids=set(),
        rejected_skill_norms=set(),
    )


def _cand(vac_id: int, *, hybrid: float) -> Candidate:
    cand = Candidate(
        vacancy_id=vac_id,
        vacancy=SimpleNamespace(
            id=vac_id, title=f"Backend {vac_id}", status="indexed", company="Acme"
        ),
        payload={
            "summary": f"summary-{vac_id}",
            "must_have_skills": ["python", "postgresql"],
            "nice_to_have_skills": ["kubernetes"],
            "requirements": ["Опыт разработки на Python от 3 лет", "Знание SQL"],
            "role_family": "software_engineering",
        },
        vector_score=0.9,
    )
    cand.hybrid_score = hybrid
    return cand


def _req_check(vacancy_id: int) -> dict:
    return {
        "must_have": [
            {"text": "Python", "status": "ok", "evidence": "коммерческий опыт 5 лет"},
            {"text": "PostgreSQL", "status": "partial", "evidence": "упомянут в проектах"},
        ],
        "nice_to_have": [
            {"text": "Kubernetes", "status": "ok", "evidence": "сертификат CKA"},
        ],
        "experience": {
            "required_years": 3,
            "candidate_years": 5.0,
            "status": "ok",
        },
    }


def _llm_payload(*vacancy_ids: int) -> dict:
    return {
        "ranked": [
            {
                "vacancy_id": vid,
                "position": i + 1,
                "confidence": 0.9 - i * 0.1,
                "requirements_check": _req_check(vid),
            }
            for i, vid in enumerate(vacancy_ids)
        ]
    }


class LLMRerankStageTest(unittest.TestCase):
    def setUp(self) -> None:
        self._was_enabled = settings.llm_rerank_enabled
        self._was_api = settings.openai_api_key
        settings.llm_rerank_enabled = True
        settings.openai_api_key = "test-key"

    def tearDown(self) -> None:
        settings.llm_rerank_enabled = self._was_enabled
        settings.openai_api_key = self._was_api

    def test_disabled_flag_is_noop(self) -> None:
        settings.llm_rerank_enabled = False
        state = MatchingState(
            resume_context=_ctx(),
            candidates=[_cand(1, hybrid=0.8)],
            diagnostics=MatchingDiagnostics(),
        )
        before = list(state.candidates)
        LLMRerankStage().run(state)
        self.assertEqual(state.candidates, before)

    def test_missing_api_key_is_noop(self) -> None:
        settings.openai_api_key = None
        state = MatchingState(
            resume_context=_ctx(),
            candidates=[_cand(1, hybrid=0.8)],
            diagnostics=MatchingDiagnostics(),
        )
        LLMRerankStage().run(state)
        self.assertEqual([c.vacancy_id for c in state.candidates], [1])
        self.assertNotIn("requirements_check", state.candidates[0].annotations)

    def test_cache_hit_reorders_and_annotates_without_calling_llm(self) -> None:
        state = MatchingState(
            resume_context=_ctx(),
            candidates=[_cand(1, hybrid=0.8), _cand(2, hybrid=0.6)],
            diagnostics=MatchingDiagnostics(),
        )
        cached = _llm_payload(2, 1)
        with (
            mock.patch.object(llm_rerank, "_budget_ok", return_value=True),
            mock.patch("app.services.rerank_cache.read", return_value=cached) as read_mock,
            mock.patch("app.services.rerank_cache.write") as write_mock,
            mock.patch.object(llm_rerank, "_call_llm") as llm_mock,
        ):
            LLMRerankStage().run(state)

        read_mock.assert_called_once()
        write_mock.assert_not_called()
        llm_mock.assert_not_called()
        self.assertEqual([c.vacancy_id for c in state.candidates], [2, 1])
        req = state.candidates[0].annotations["requirements_check"]
        self.assertIn("must_have", req)
        self.assertIn("nice_to_have", req)
        self.assertIn("experience", req)
        self.assertAlmostEqual(state.candidates[0].annotations["llm_confidence"], 0.9)
        self.assertEqual(state.diagnostics.custom.get("llm_rerank_cache_hit"), 1)

    def test_cache_miss_calls_llm_and_writes_result(self) -> None:
        state = MatchingState(
            resume_context=_ctx(),
            candidates=[_cand(1, hybrid=0.7), _cand(2, hybrid=0.6)],
            diagnostics=MatchingDiagnostics(),
        )
        llm_result = _llm_payload(2, 1)
        with (
            mock.patch.object(llm_rerank, "_budget_ok", return_value=True),
            mock.patch("app.services.rerank_cache.read", return_value=None),
            mock.patch("app.services.rerank_cache.write") as write_mock,
            mock.patch.object(llm_rerank, "_call_llm", return_value=llm_result) as llm_mock,
        ):
            LLMRerankStage().run(state)

        llm_mock.assert_called_once()
        write_mock.assert_called_once()
        self.assertEqual([c.vacancy_id for c in state.candidates], [2, 1])
        self.assertEqual(state.diagnostics.custom.get("llm_rerank_applied"), 2)
        self.assertGreaterEqual(state.candidates[0].hybrid_score, state.candidates[1].hybrid_score)

    def test_llm_failure_falls_back_and_marks_skipped(self) -> None:
        state = MatchingState(
            resume_context=_ctx(),
            candidates=[_cand(1, hybrid=0.7)],
            diagnostics=MatchingDiagnostics(),
        )
        with (
            mock.patch.object(llm_rerank, "_budget_ok", return_value=True),
            mock.patch("app.services.rerank_cache.read", return_value=None),
            mock.patch.object(llm_rerank, "_call_llm", side_effect=RuntimeError("openai down")),
        ):
            LLMRerankStage().run(state)

        self.assertTrue(state.candidates[0].annotations.get("rerank_skipped"))
        self.assertEqual(state.diagnostics.custom.get("llm_rerank_fallback"), 1)

    def test_budget_exhausted_skips_and_annotates(self) -> None:
        state = MatchingState(
            resume_context=_ctx(),
            candidates=[_cand(1, hybrid=0.8), _cand(2, hybrid=0.6)],
            diagnostics=MatchingDiagnostics(),
        )
        with (
            mock.patch.object(llm_rerank, "_budget_ok", return_value=False),
            mock.patch.object(llm_rerank, "_call_llm") as llm_mock,
        ):
            LLMRerankStage().run(state)

        llm_mock.assert_not_called()
        for cand in state.candidates:
            self.assertTrue(cand.annotations.get("rerank_skipped"))
        self.assertEqual(state.diagnostics.custom.get("llm_rerank_skipped_budget"), 1)

    def test_splice_head_preserves_dropped_and_tail(self) -> None:
        head1 = _cand(1, hybrid=0.8)
        head2 = _cand(2, hybrid=0.7)
        tail = _cand(3, hybrid=0.4)
        dropped = _cand(4, hybrid=0.9)
        dropped.drop_reason = "domain_mismatch"
        state = MatchingState(
            resume_context=_ctx(),
            candidates=[head1, head2, tail, dropped],
            diagnostics=MatchingDiagnostics(),
        )
        cached = _llm_payload(2, 1)
        with (
            mock.patch.object(settings, "llm_rerank_top_k", 2),
            mock.patch.object(llm_rerank, "_budget_ok", return_value=True),
            mock.patch("app.services.rerank_cache.read", return_value=cached),
            mock.patch("app.services.rerank_cache.write"),
        ):
            LLMRerankStage().run(state)

        ids_in_order = [c.vacancy_id for c in state.candidates]
        self.assertEqual(ids_in_order, [2, 1, 3, 4])
        self.assertEqual(state.candidates[3].drop_reason, "domain_mismatch")

    def test_unranked_leftovers_preserved_at_end_of_head(self) -> None:
        head1 = _cand(1, hybrid=0.8)
        head2 = _cand(2, hybrid=0.7)
        state = MatchingState(
            resume_context=_ctx(),
            candidates=[head1, head2],
            diagnostics=MatchingDiagnostics(),
        )
        cached = _llm_payload(1)
        with (
            mock.patch.object(llm_rerank, "_budget_ok", return_value=True),
            mock.patch("app.services.rerank_cache.read", return_value=cached),
            mock.patch("app.services.rerank_cache.write"),
        ):
            LLMRerankStage().run(state)

        self.assertEqual([c.vacancy_id for c in state.candidates], [1, 2])

    def test_requirements_check_shape_is_correct(self) -> None:
        state = MatchingState(
            resume_context=_ctx(),
            candidates=[_cand(1, hybrid=0.8)],
            diagnostics=MatchingDiagnostics(),
        )
        llm_result = _llm_payload(1)
        with (
            mock.patch.object(llm_rerank, "_budget_ok", return_value=True),
            mock.patch("app.services.rerank_cache.read", return_value=None),
            mock.patch("app.services.rerank_cache.write"),
            mock.patch.object(llm_rerank, "_call_llm", return_value=llm_result),
        ):
            LLMRerankStage().run(state)

        cand = state.candidates[0]
        req = cand.annotations.get("requirements_check")
        self.assertIsInstance(req, dict)
        self.assertIsInstance(req["must_have"], list)
        self.assertIsInstance(req["nice_to_have"], list)
        # experience may be dict or None
        self.assertIn("experience", req)
        for item in req["must_have"]:
            self.assertIn(item["status"], {"ok", "partial", "missing", "unknown"})
            self.assertIsInstance(item["text"], str)
            self.assertIsInstance(item["evidence"], str)

    def test_requirements_check_list_capped_at_12(self) -> None:
        oversized_check = {
            "must_have": [
                {"text": f"req-{i}", "status": "ok", "evidence": "присутствует"}
                for i in range(15)
            ],
            "nice_to_have": [
                {"text": f"nice-{i}", "status": "missing", "evidence": "отсутствует"}
                for i in range(14)
            ],
            "experience": None,
        }
        result = {
            "ranked": [
                {
                    "vacancy_id": 1,
                    "position": 1,
                    "confidence": 0.8,
                    "requirements_check": oversized_check,
                }
            ]
        }
        state = MatchingState(
            resume_context=_ctx(),
            candidates=[_cand(1, hybrid=0.8)],
            diagnostics=MatchingDiagnostics(),
        )
        with (
            mock.patch.object(llm_rerank, "_budget_ok", return_value=True),
            mock.patch("app.services.rerank_cache.read", return_value=None),
            mock.patch("app.services.rerank_cache.write"),
            mock.patch.object(llm_rerank, "_call_llm", return_value=result),
        ):
            LLMRerankStage().run(state)

        req = state.candidates[0].annotations["requirements_check"]
        self.assertLessEqual(len(req["must_have"]), 12)
        self.assertLessEqual(len(req["nice_to_have"]), 12)


if __name__ == "__main__":
    unittest.main()
