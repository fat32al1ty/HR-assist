from __future__ import annotations

import unittest

from app.services.matching.stages.dedupe import DedupeStage

from .conftest import make_candidate, make_context, make_state


class DedupeStageTest(unittest.TestCase):
    def test_identical_title_company_drops_second(self) -> None:
        ctx = make_context()
        cands = [
            make_candidate(1, title="Backend Developer", company="Acme"),
            make_candidate(2, title="Backend Developer", company="Acme"),
        ]
        state = make_state(ctx, cands)
        DedupeStage().run(state)
        self.assertFalse(state.candidates[0].drop_reason)
        self.assertEqual(state.candidates[1].drop_reason, "dedupe")
        self.assertEqual(state.diagnostics.drop_dedupe, 1)

    def test_different_company_same_title_both_survive(self) -> None:
        ctx = make_context()
        cands = [
            make_candidate(1, title="Backend Developer", company="Acme"),
            make_candidate(2, title="Backend Developer", company="Globex"),
        ]
        state = make_state(ctx, cands)
        DedupeStage().run(state)
        self.assertFalse(state.candidates[0].drop_reason)
        self.assertFalse(state.candidates[1].drop_reason)

    def test_case_insensitive_matching(self) -> None:
        ctx = make_context()
        cands = [
            make_candidate(1, title="Backend Developer", company="Acme"),
            make_candidate(2, title="  BACKEND developer  ", company="acme"),
        ]
        state = make_state(ctx, cands)
        DedupeStage().run(state)
        self.assertEqual(state.candidates[1].drop_reason, "dedupe")


if __name__ == "__main__":
    unittest.main()
