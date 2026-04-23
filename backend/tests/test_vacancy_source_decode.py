"""The vacancy source fetcher must refuse to return mojibake.

Prior to this contract, a non-UTF-8 response would silently fall back to
httpx's charset auto-detection, and the garbled text flowed into embeddings.
This test locks in the new behavior: raise VacancyFetchError on undecodable
bytes, log the failure, and increment the parse-error counter so the job
metrics surface it.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import httpx

from app.services import vacancy_sources
from app.services.vacancy_sources import (
    VacancyFetchError,
    VacancyParseStats,
    _fetch_text,
    _enrich_preview,
    vacancy_parse_stats_scope,
)


def _response(content: bytes, *, charset: str | None = None) -> httpx.Response:
    headers = {}
    if charset is not None:
        headers["content-type"] = f"text/html; charset={charset}"
    else:
        headers["content-type"] = "text/html"
    return httpx.Response(
        200,
        content=content,
        headers=headers,
        request=httpx.Request("GET", "https://example.test/vacancy/1"),
    )


class FetchTextDecodeTest(unittest.TestCase):
    def test_utf8_content_returns_clean_text(self) -> None:
        text = "Привет, вакансия"
        fake = _response(text.encode("utf-8"))
        with patch.object(vacancy_sources.httpx, "get", return_value=fake):
            result = _fetch_text("https://example.test/vacancy/1", source="hh_public")
        self.assertEqual(result, text)

    def test_declared_non_utf8_charset_is_honored(self) -> None:
        text = "Привет, вакансия"
        fake = _response(text.encode("windows-1251"), charset="windows-1251")
        with patch.object(vacancy_sources.httpx, "get", return_value=fake):
            result = _fetch_text("https://example.test/vacancy/1", source="hh_public")
        self.assertEqual(result, text)

    def test_undecodable_bytes_raise_vacancy_fetch_error(self) -> None:
        # Random bytes that are not valid UTF-8 and have no declared charset.
        garbled = bytes([0xC3, 0x28, 0xA0, 0xA1, 0xE2, 0x28, 0xA1])
        fake = _response(garbled)
        with patch.object(vacancy_sources.httpx, "get", return_value=fake):
            with self.assertRaises(VacancyFetchError) as context:
                _fetch_text("https://example.test/vacancy/1", source="hh_public")
        self.assertEqual(context.exception.source, "hh_public")
        self.assertIn("https://example.test/vacancy/1", str(context.exception))

    def test_parse_stats_scope_records_skip_on_decode_failure(self) -> None:
        """Decode failure inside _enrich_preview must increment stats, not pollute raw_text."""
        garbled = bytes([0xC3, 0x28, 0xA0, 0xA1])
        fake = _response(garbled)

        items = [
            {
                "source": "hh_public",
                "source_url": "https://example.test/vacancy/42",
                "title": "Clean title",
                "company": None,
                "location": None,
                "raw_payload": {},
                "raw_text": None,
            }
        ]

        stats = VacancyParseStats()
        with patch.object(vacancy_sources.httpx, "get", return_value=fake):
            with vacancy_parse_stats_scope(stats):
                enriched = _enrich_preview(items)

        self.assertEqual(len(enriched), 1)
        # Listing metadata survives; raw_text is NOT polluted with garbled content.
        self.assertIsNone(enriched[0].get("raw_text"))
        self.assertEqual(stats.skipped_parse_errors, 1)
        self.assertEqual(stats.samples[0]["source"], "hh_public")
        self.assertEqual(stats.samples[0]["url"], "https://example.test/vacancy/42")


if __name__ == "__main__":
    unittest.main()
