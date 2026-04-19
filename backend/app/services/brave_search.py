from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import settings


class BraveSearchUnavailable(RuntimeError):
    pass


POSITIVE_URL_MARKERS = (
    "/vacancy",
    "/vacancies",
    "/jobs",
    "/job",
    "/career",
    "/careers",
    "/rabota",
    "/vakans",
)

NEGATIVE_URL_MARKERS = (
    "/blog",
    "/article",
    "/articles",
    "/news",
    "/about",
    "/pricing",
    "/docs",
    "/help",
    "/support",
    "/wiki",
)

POSITIVE_TEXT_MARKERS = (
    "вакан",
    "работа",
    "должност",
    "позици",
    "требован",
    "обязанност",
    "job",
    "vacancy",
    "hiring",
    "requirements",
    "responsibilities",
)

NEGATIVE_TEXT_MARKERS = (
    "статья",
    "обзор",
    "новость",
    "чеклист",
    "guide",
    "tutorial",
    "documentation",
    "docs",
)


def _normalize_company(url: str) -> str | None:
    hostname = urlparse(url).hostname
    if not hostname:
        return None
    company = hostname.replace("www.", "").split(".")[0]
    return company if company else None


def _is_probable_vacancy(url: str, title: str, raw_text: str | None) -> bool:
    source = f"{title}\n{raw_text or ''}".lower()
    normalized_url = url.lower()

    has_positive_url = any(marker in normalized_url for marker in POSITIVE_URL_MARKERS)
    has_positive_text = any(marker in source for marker in POSITIVE_TEXT_MARKERS)
    has_negative_url = any(marker in normalized_url for marker in NEGATIVE_URL_MARKERS)
    has_negative_text = any(marker in source for marker in NEGATIVE_TEXT_MARKERS)

    if has_negative_url and not has_positive_url:
        return False
    if has_negative_text and not has_positive_text:
        return False
    return has_positive_url or has_positive_text


def search_vacancies_with_brave(*, query: str, count: int) -> list[dict[str, Any]]:
    if not settings.brave_api_key:
        raise BraveSearchUnavailable("Brave API key is not configured")

    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": settings.brave_api_key,
    }
    params = {
        "q": f"{query} вакансии",
        "count": count,
        "search_lang": "ru",
    }

    try:
        response = httpx.get(
            settings.brave_web_search_url,
            params=params,
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
    except Exception as error:
        raise BraveSearchUnavailable(f"Could not fetch vacancies from Brave Search API: {error}") from error

    payload = response.json()
    results = payload.get("web", {}).get("results", [])

    vacancies: list[dict[str, Any]] = []
    for result in results:
        url = result.get("url")
        title = result.get("title")
        if not url or not title:
            continue

        summary_parts = [result.get("description", "")]
        summary_parts.extend(result.get("extra_snippets") or [])
        raw_text = "\n".join(part for part in summary_parts if part).strip()
        if not _is_probable_vacancy(url, title, raw_text):
            continue

        vacancies.append(
            {
                "source": "brave",
                "source_url": url,
                "title": title.strip()[:512],
                "company": _normalize_company(url),
                "location": None,
                "raw_payload": result,
                "raw_text": raw_text or None,
            }
        )
    return vacancies
