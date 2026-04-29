"""v0.23.0: log_openai_call writes a row + must not raise on DB hiccup."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.openai_call_log import OpenaiCallLog
from app.services.openai_usage import log_openai_call


class OpenaiCallLogPersistenceTest(unittest.TestCase):
    def test_call_log_row_written(self) -> None:
        marker = f"test-marker-{id(self)}"
        log_openai_call(
            model=marker,
            prompt_tokens=42,
            completion_tokens=7,
            cost_usd=0.000123,
            user_id=None,
            duration_ms=999,
        )
        db = SessionLocal()
        try:
            row = db.scalar(select(OpenaiCallLog).where(OpenaiCallLog.model == marker).limit(1))
            self.assertIsNotNone(row)
            self.assertEqual(row.prompt_tokens, 42)
            self.assertEqual(row.completion_tokens, 7)
            self.assertEqual(int(row.duration_ms), 999)
            db.delete(row)
            db.commit()
        finally:
            db.close()

    def test_db_failure_does_not_raise(self) -> None:
        # Force the local SessionLocal() inside log_openai_call to blow up.
        with patch("app.db.session.SessionLocal", side_effect=RuntimeError("db down")):
            try:
                log_openai_call(
                    model="will-not-persist",
                    prompt_tokens=1,
                    completion_tokens=1,
                    cost_usd=0.0,
                    user_id=None,
                    duration_ms=1,
                )
            except Exception as exc:
                self.fail(f"log_openai_call raised when DB was down: {exc}")


if __name__ == "__main__":
    unittest.main()
