from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from app.services.matching.stages.filter import HardFilterStage

from .conftest import make_candidate, make_context, make_state


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class HardFilterStageTest(unittest.TestCase):
    def _stage(self):
        db = _FakeSession()
        vector_store = MagicMock()
        return HardFilterStage(db=db, vector_store=vector_store), db, vector_store

    def test_listing_page_dropped(self) -> None:
        ctx = make_context()
        # Listing-page detection runs AFTER non-vacancy-page; for hh.ru that
        # means the URL must contain /vacancy/ (singular) to clear the
        # earlier guard. A title starting with "Работа " then trips the
        # listing-page rule.
        cand = make_candidate(
            1,
            title="Работа Python разработчик",
            source_url="https://hh.ru/vacancy/search?keyword=python",
        )
        state = make_state(ctx, [cand])
        stage, _, _ = self._stage()
        stage.run(state)
        self.assertEqual(cand.drop_reason, "listing_page")
        self.assertEqual(state.diagnostics.drop_listing_page, 1)

    def test_archived_vacancy_is_persisted_and_evicted(self) -> None:
        ctx = make_context()
        cand = make_candidate(
            1,
            title="Archived position",
            source_url="https://hh.ru/vacancy/999",
            raw_text="вакансия в архиве",
        )
        state = make_state(ctx, [cand])
        stage, db, vs = self._stage()
        stage.run(state)
        self.assertEqual(cand.drop_reason, "archived")
        self.assertEqual(state.diagnostics.drop_archived, 1)
        self.assertEqual(cand.vacancy.status, "filtered")
        self.assertTrue(db.committed)
        vs.delete_vacancy_profile.assert_called_once_with(vacancy_id=1)

    def test_host_not_allowed_dropped(self) -> None:
        ctx = make_context()
        cand = make_candidate(
            1,
            title="Developer",
            source_url="https://evil.example.com/vacancy/1",
        )
        state = make_state(ctx, [cand])
        stage, _, _ = self._stage()
        stage.run(state)
        self.assertEqual(cand.drop_reason, "host_not_allowed")

    def test_work_format_mismatch_with_remote_preference(self) -> None:
        ctx = make_context(
            preferences={"preferred_work_format": "remote", "relocation_mode": "home_only"}
        )
        cand = make_candidate(
            1,
            title="Middle Python Developer",
            source_url="https://hh.ru/vacancy/100",
            payload={"remote_policy": "office"},
        )
        state = make_state(ctx, [cand])
        stage, _, _ = self._stage()
        stage.run(state)
        self.assertEqual(cand.drop_reason, "work_format")
        self.assertEqual(state.diagnostics.drop_work_format, 1)

    def test_clean_vacancy_survives(self) -> None:
        ctx = make_context(resume_skills={"python", "django"})
        cand = make_candidate(
            1,
            title="Middle Python Developer",
            source_url="https://hh.ru/vacancy/100",
            payload={"must_have_skills": ["python"]},
        )
        state = make_state(ctx, [cand])
        stage, _, _ = self._stage()
        stage.run(state)
        self.assertFalse(cand.drop_reason)


if __name__ == "__main__":
    unittest.main()
