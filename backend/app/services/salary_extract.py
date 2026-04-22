"""Extract stated salary from vacancy raw payloads.

Phase 2.7. HH's ``raw_payload.salary`` / ``salary_range`` objects are
the single reliable source — SuperJob and Habr scrape the page body
and don't expose structured salary, and Brave never does. For non-HH
sources we try a loose ruble-regex fallback on the raw text.

All numbers come back as integers; ``currency`` is normalised to a
3-letter uppercase code (HH's legacy ``"RUR"`` becomes ``"RUB"``).
"""

from __future__ import annotations

import re
from typing import Any

# Unicode explicit on purpose — the Cyrillic "ruble" abbreviations
# and the thin/non-breaking spaces HH uses inside numbers need to be
# literal, not source-form, to survive formatter round-trips.
_RUB_SYMBOL = "₽"  # ₽
_EN_DASH = "–"  # –
_EM_DASH = "—"  # —
_NBSP = " "

_NUMBER = rf"\d{{2,3}}(?:[\s{_NBSP}]?\d{{3}})+"
_SEPARATOR = rf"(?:\s*[-{_EN_DASH}{_EM_DASH}]\s*|\s+до\s+)"  # "-" or " до "
_CURRENCY = rf"\s*(?:{_RUB_SYMBOL}|руб\.?|р\.|rub)(?!\w)"

_RUBLE_RANGE = re.compile(
    rf"(?P<low>{_NUMBER}){_SEPARATOR}(?P<high>{_NUMBER}){_CURRENCY}",
    re.IGNORECASE,
)
_RUBLE_SINGLE = re.compile(rf"(?P<low>{_NUMBER}){_CURRENCY}", re.IGNORECASE)

CURRENCY_ALIASES = {"RUR": "RUB", "RUB": "RUB", "USD": "USD", "EUR": "EUR"}


class ExtractedSalary(tuple):
    """``(min, max, currency, gross)`` — fields optional except currency.

    Tuple subclass so the result is structurally stable and trivially
    splattable into SQL upserts.
    """

    __slots__ = ()

    def __new__(
        cls,
        salary_min: int | None,
        salary_max: int | None,
        currency: str | None,
        gross: bool | None,
    ) -> ExtractedSalary:
        return super().__new__(cls, (salary_min, salary_max, currency, gross))

    @property
    def salary_min(self) -> int | None:
        return self[0]

    @property
    def salary_max(self) -> int | None:
        return self[1]

    @property
    def currency(self) -> str | None:
        return self[2]

    @property
    def gross(self) -> bool | None:
        return self[3]

    def is_present(self) -> bool:
        return self.salary_min is not None or self.salary_max is not None


def extract_from_hh_payload(payload: dict[str, Any]) -> ExtractedSalary:
    """Read HH's ``salary`` or ``salary_range`` dict into a normalised tuple.

    HH returns the more recent ``salary_range`` when available; both
    have the same shape (``from``, ``to``, ``currency``, ``gross``).
    Prefer ``salary_range`` because it is closer to the stated band.
    """
    sal = payload.get("salary_range") or payload.get("salary")
    if not isinstance(sal, dict):
        return ExtractedSalary(None, None, None, None)
    low = _coerce_int(sal.get("from"))
    high = _coerce_int(sal.get("to"))
    if low is None and high is None:
        return ExtractedSalary(None, None, None, None)
    currency = CURRENCY_ALIASES.get((sal.get("currency") or "").upper())
    gross = sal.get("gross")
    if not isinstance(gross, bool):
        gross = None
    return ExtractedSalary(low, high, currency, gross)


def extract_from_text(text: str | None) -> ExtractedSalary:
    """Best-effort ruble-band parse from free-form vacancy text.

    Catches the common hh/superjob-style "от 180 000 до 260 000 руб."
    and the shorthand "180 000–260 000 ₽". Returns nothing when the
    only number looks like a phone number, year, or id.
    """
    if not text:
        return ExtractedSalary(None, None, None, None)
    low: int | None = None
    high: int | None = None
    match = _RUBLE_RANGE.search(text)
    if match:
        low = _coerce_int(match.group("low"))
        high = _coerce_int(match.group("high"))
    else:
        match = _RUBLE_SINGLE.search(text)
        if match:
            low = _coerce_int(match.group("low"))
    if low is None:
        return ExtractedSalary(None, None, None, None)
    # Real Russian IT salaries in 2026 sit comfortably between 30k and
    # 5M ₽/mo. Anything outside that is almost certainly not a monthly
    # comp number (could be annual turnover, id, phone, etc.).
    if low < 20_000 or low > 5_000_000:
        return ExtractedSalary(None, None, None, None)
    if high is not None and (high < low or high > 5_000_000):
        high = None
    return ExtractedSalary(low, high, "RUB", None)


def extract_for_vacancy(
    source: str,
    raw_payload: dict[str, Any] | None,
    raw_text: str | None = None,
) -> ExtractedSalary:
    """Dispatch on source, falling back to a text scan."""
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    if source == "hh_api":
        hh = extract_from_hh_payload(payload)
        if hh.is_present():
            return hh
    return extract_from_text(raw_text)


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        ivalue = int(value)
        return ivalue if ivalue > 0 else None
    if isinstance(value, str):
        cleaned = re.sub(rf"[\s{_NBSP}]", "", value)
        if not cleaned.isdigit():
            return None
        ivalue = int(cleaned)
        return ivalue if ivalue > 0 else None
    return None


def classify_fit(
    salary_mid: int | None,
    *,
    expected_min: int | None,
    expected_max: int | None,
    currency: str | None,
    expected_currency: str,
) -> tuple[str, float]:
    """Map ``(vacancy mid, user expectation)`` → ``(tag, soft penalty)``.

    Tags: ``match`` | ``below`` | ``above`` | ``unknown``. Penalty is
    in ``[0, 0.25]`` and should be subtracted from the hybrid score
    by the caller. We never hard-drop — the user might have undervalued
    themselves, and the card still has other signal.
    """
    if salary_mid is None:
        return ("unknown", 0.0)
    if expected_min is None and expected_max is None:
        return ("unknown", 0.0)
    if currency and expected_currency and currency != expected_currency:
        return ("unknown", 0.0)
    if expected_min is not None and salary_mid < expected_min:
        gap = (expected_min - salary_mid) / max(expected_min, 1)
        penalty = min(0.25, max(0.0, gap * 0.5))
        return ("below", penalty)
    if expected_max is not None and salary_mid > expected_max * 1.5:
        gap = (salary_mid - expected_max * 1.5) / max(expected_max, 1)
        penalty = min(0.15, max(0.0, gap * 0.3))
        return ("above", penalty)
    return ("match", 0.0)
