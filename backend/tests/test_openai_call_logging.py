"""Every OpenAI call must emit exactly one structured OPENAI_CALL JSON log line.

This is the contract test: future refactors that accidentally drop logging
(or wrap it in a silent try/except) break this test loudly.
"""

from __future__ import annotations

import json
import logging
import unittest

from app.services.openai_usage import (
    OPENAI_CALL_EVENT,
    OPENAI_CALL_LOGGER,
    record_embeddings_usage,
    record_responses_usage,
)


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


class OpenAICallLoggingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.capture = _Capture()
        self._previous_level = OPENAI_CALL_LOGGER.level
        OPENAI_CALL_LOGGER.setLevel(logging.INFO)
        OPENAI_CALL_LOGGER.addHandler(self.capture)

    def tearDown(self) -> None:
        OPENAI_CALL_LOGGER.removeHandler(self.capture)
        OPENAI_CALL_LOGGER.setLevel(self._previous_level)

    def _parse_lines(self) -> list[dict]:
        parsed: list[dict] = []
        for line in self.capture.lines:
            parsed.append(json.loads(line))
        return parsed

    def test_record_responses_usage_logs_one_line(self) -> None:
        record_responses_usage(
            input_tokens=1500,
            output_tokens=800,
            model="gpt-5.4-mini",
            duration_ms=420,
        )
        events = self._parse_lines()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["event"], OPENAI_CALL_EVENT)
        self.assertEqual(event["model"], "gpt-5.4-mini")
        self.assertEqual(event["prompt_tokens"], 1500)
        self.assertEqual(event["completion_tokens"], 800)
        self.assertEqual(event["duration_ms"], 420)
        self.assertGreater(event["cost_usd"], 0.0)
        # user_id may be None when no budget scope is active — that's acceptable.
        self.assertIn("user_id", event)

    def test_record_embeddings_usage_logs_one_line(self) -> None:
        record_embeddings_usage(
            input_tokens=3000,
            model="text-embedding-3-large",
            duration_ms=120,
        )
        events = self._parse_lines()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["event"], OPENAI_CALL_EVENT)
        self.assertEqual(event["prompt_tokens"], 3000)
        self.assertEqual(event["completion_tokens"], 0)
        self.assertEqual(event["model"], "text-embedding-3-large")
        self.assertGreaterEqual(event["cost_usd"], 0.0)


if __name__ == "__main__":
    unittest.main()
