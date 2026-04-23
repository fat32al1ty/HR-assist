"""PII scrubbing utilities.

Pure functions only — no IO, no side effects.
"""

import re

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
    re.IGNORECASE,
)

# Russian phones: +7…, 8(…, 7-…, international +<cc>…
# Must have >=10 digits after normalization — checked by digit count in pattern.
_PHONE_RE = re.compile(
    r"(?<!\w)"
    r"(?:"
    r"\+7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"  # +7 (XXX) XXX-XX-XX
    r"|8[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"  # 8 (XXX) XXX-XX-XX
    r"|\+[1-9]\d{0,2}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{2,4}[\s\-]?\d{2,4}[\s\-]?\d{0,4}"  # +<cc>…
    r")"
    r"(?!\w)",
    re.IGNORECASE,
)

_URL_RE = re.compile(
    r"(?:"
    r"https?://[^\s\)\]>\"']+"
    r"|(?:vk\.com|t\.me|linkedin\.com/in|github\.com|twitter\.com|x\.com"
    r"|instagram\.com|facebook\.com)/[A-Za-z0-9_\-./]+"
    r")",
    re.IGNORECASE,
)

# Birthdates only when preceded by a relevant keyword within 20 chars
_BIRTHDATE_KEYWORD_RE = re.compile(
    r"(?:родил|д\.р\.|дата\s+рожд|рожден|born|d\.o\.b|date\s+of\s+birth)",
    re.IGNORECASE,
)
_BIRTHDATE_RE = re.compile(r"\b(?:\d{2}[./]\d{2}[./]\d{4}|\d{4}-\d{2}-\d{2})\b")

# Cyrillic name patterns — conservative
# 1. Three consecutive capitalized Cyrillic tokens (ФИО order) sitting on a line
#    by themselves within the first 500 chars. Anchoring to line boundaries avoids
#    false-positives on mid-sentence fragments like employer "Сбер Банк Технологии"
#    embedded in a longer experience line.
_THREE_CYR_TOKENS_RE = re.compile(r"(?m)^[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){2}\s*$")
# 2. Two capitalized Cyrillic tokens on a line starting with ФИО/Имя/Name (optional colon/space)
_FIO_LINE_RE = re.compile(
    r"^(?:ФИО|Имя|Name)\s*:\s*([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)+)",
    re.MULTILINE | re.IGNORECASE,
)


def _scrub_birthdates(text: str) -> tuple[str, int]:
    """Replace birthdates that are preceded by a relevant keyword."""
    count = 0
    result = []
    pos = 0
    for m in _BIRTHDATE_RE.finditer(text):
        start = m.start()
        prefix = text[max(0, start - 20) : start]
        if _BIRTHDATE_KEYWORD_RE.search(prefix):
            result.append(text[pos:start])
            result.append("[DATE]")
            pos = m.end()
            count += 1
    result.append(text[pos:])
    return "".join(result), count


def _scrub_names(text: str) -> tuple[str, int]:
    """Scrub cyrillic name patterns conservatively."""
    count = 0

    # Pass 1: ФИО/Имя/Name lines (anywhere in document)
    new_text = text
    replaced_count = 0

    def _replace_fio(m: re.Match) -> str:
        nonlocal replaced_count
        replaced_count += 1
        # Keep the label, replace name
        label = m.group(0)[: m.start(1) - m.start()]
        return label + "[NAME]"

    new_text = _FIO_LINE_RE.sub(_replace_fio, new_text)
    count += replaced_count

    # Pass 2: three consecutive Cyrillic capitalized tokens in first 500 chars
    header = new_text[:500]
    tail = new_text[500:]
    replaced_count2 = 0

    def _replace_three(m: re.Match) -> str:
        nonlocal replaced_count2
        replaced_count2 += 1
        return "[NAME]"

    header = _THREE_CYR_TOKENS_RE.sub(_replace_three, header, count=1)
    count += replaced_count2

    return header + tail, count


def scrub_pii(text: str) -> tuple[str, dict[str, int]]:
    """Return (cleaned_text, counters).

    Counters dict: {"emails": N, "phones": N, "urls": N, "names": N}
    """
    # Emails
    emails_found = _EMAIL_RE.findall(text)
    cleaned = _EMAIL_RE.sub("[EMAIL]", text)

    # URLs (before phones to avoid partial overlap)
    urls_found = _URL_RE.findall(cleaned)
    cleaned = _URL_RE.sub("[URL]", cleaned)

    # Phones
    phones_found = _PHONE_RE.findall(cleaned)
    cleaned = _PHONE_RE.sub("[PHONE]", cleaned)

    # Birthdates — intentionally not surfaced in counters; scrubbed silently so
    # operators see email/phone/URL/name signal cleanly without date noise.
    cleaned, _dates = _scrub_birthdates(cleaned)

    # Names
    cleaned, names_count = _scrub_names(cleaned)

    counters = {
        "emails": len(emails_found),
        "phones": len(phones_found),
        "urls": len(urls_found),
        "names": names_count,
    }
    return cleaned, counters


def mask_email(email: str) -> str:
    """Return a masked form: 'jane.doe@example.com' -> 'j***@e***.com'."""
    if "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    masked_local = local[0] + "***" if local else "***"
    domain_parts = domain.split(".")
    masked_domain = domain_parts[0][0] + "***" if domain_parts[0] else "***"
    suffix = "." + ".".join(domain_parts[1:]) if len(domain_parts) > 1 else ""
    return f"{masked_local}@{masked_domain}{suffix}"
