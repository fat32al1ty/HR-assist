from __future__ import annotations

import html
import logging
import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote_plus, urljoin, urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class VacancyFetchError(RuntimeError):
    """Raised when a vacancy source URL can't be decoded into clean UTF-8 text.

    Previously the code silently fell back to httpx's charset auto-detection,
    which dumped mojibake into embeddings. Now we fail loudly so callers can
    log+skip the polluted record and increment a visible counter.
    """

    def __init__(self, *, url: str, source: str, reason: str) -> None:
        self.url = url
        self.source = source
        self.reason = reason
        super().__init__(f"Vacancy fetch failed for {source} {url}: {reason}")


@dataclass
class VacancyParseStats:
    skipped_parse_errors: int = 0
    hh_fetched_raw: int = 0
    search_dedup_skipped: int = 0
    search_strict_rejected: int = 0
    enrich_failed: int = 0
    pages_truncated_by_indexed: int = 0
    samples: list[dict[str, str]] = field(default_factory=list)

    def record_skip(self, *, source: str, url: str, reason: str) -> None:
        self.skipped_parse_errors += 1
        # Keep a small, bounded sample so operators can spot which sources
        # actually fail without blowing up the job record.
        if len(self.samples) < 10:
            self.samples.append({"source": source, "url": url, "reason": reason})

    def record_hh_fetched(self, delta: int) -> None:
        self.hh_fetched_raw += max(0, delta)

    def record_dedup(self) -> None:
        self.search_dedup_skipped += 1

    def record_strict_reject(self) -> None:
        self.search_strict_rejected += 1

    def record_enrich_fail(self) -> None:
        self.enrich_failed += 1

    def record_page_truncated_by_indexed(self) -> None:
        self.pages_truncated_by_indexed += 1


_PARSE_STATS: ContextVar[VacancyParseStats | None] = ContextVar("vacancy_parse_stats", default=None)


@contextmanager
def vacancy_parse_stats_scope(stats: VacancyParseStats | None = None):
    """Make a VacancyParseStats instance available to source fetchers in scope."""
    target = stats if stats is not None else VacancyParseStats()
    token = _PARSE_STATS.set(target)
    try:
        yield target
    finally:
        _PARSE_STATS.reset(token)


def _record_parse_skip(*, source: str, url: str, reason: str) -> None:
    stats = _PARSE_STATS.get()
    if stats is None:
        return
    stats.record_skip(source=source, url=url, reason=reason)


def _record_enrich_fail() -> None:
    stats = _PARSE_STATS.get()
    if stats is None:
        return
    stats.record_enrich_fail()


REQUEST_HEADERS = {
    "User-Agent": "HR-Assist-Bot/1.0 (+https://github.com/fat32al1ty/HR-assist)",
    "Accept-Language": "ru,en;q=0.9",
}
MAX_PUBLIC_SOURCE_PAGES = 3
MAX_API_SOURCE_PAGES = 3
MAX_PREVIEW_ENRICH = 4
FETCH_TIMEOUT_SECONDS = 4
ENRICH_TIME_BUDGET_SECONDS = 4
HH_PUBLIC_API_URL = "https://api.hh.ru/vacancies"
HH_CONCURRENCY = 3
# Level 2 D1: stop HH pagination once the already-indexed ratio on a page
# crosses this threshold. Further pages are extremely likely to return the
# same stale inventory — keep API round-trips bounded and surface the event
# in the funnel via ``pages_truncated_by_indexed``.
ALREADY_INDEXED_BREAK_RATIO = 0.9
ALREADY_INDEXED_BREAK_MIN_PAGE_SIZE = 20
ALLOWED_JOB_HOSTS = (
    "hh.ru",
    "career.habr.com",
    "superjob.ru",
)
BLOCKED_JOB_HOSTS = (
    "djinni.co",
    "workingnomads.com",
)
STRICT_QUERY_MATCH_SOURCES = {"superjob", "superjob_public", "habr_public", "hh_public"}
SEARCH_TOKEN_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "developer",
    "engineer",
    "remote",
    "full",
    "time",
    "senior",
    "middle",
    "junior",
    "россия",
    "вакансия",
    "работа",
    "удаленно",
}


def _to_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _strip_html(value: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", value)
    cleaned = re.sub(r"\s+", " ", html.unescape(no_tags)).strip()
    return cleaned


def _tokenize_for_match(value: str | None) -> set[str]:
    if not value:
        return set()
    normalized = value.lower()
    for ch in ["/", "-", ",", ".", ":", ";", "(", ")", "[", "]", "|", "+"]:
        normalized = normalized.replace(ch, " ")
    tokens = [token.strip() for token in normalized.split()]
    output: set[str] = set()
    for token in tokens:
        if len(token) < 3:
            continue
        if token in SEARCH_TOKEN_STOPWORDS:
            continue
        output.add(token)
    return output


def _query_matches_item(query: str, item: dict[str, Any]) -> bool:
    query_tokens = _tokenize_for_match(query)
    if not query_tokens:
        return True

    title_tokens = _tokenize_for_match(_to_str(item.get("title")))
    company_tokens = _tokenize_for_match(_to_str(item.get("company")))
    location_tokens = _tokenize_for_match(_to_str(item.get("location")))
    raw_tokens = _tokenize_for_match(_to_str(item.get("raw_text")))
    item_tokens = title_tokens.union(company_tokens).union(location_tokens).union(raw_tokens)
    if not item_tokens:
        return False

    overlap = query_tokens.intersection(item_tokens)
    if overlap:
        return True

    compact_item_text = " ".join(
        part
        for part in [
            _to_str(item.get("title")),
            _to_str(item.get("company")),
            _to_str(item.get("raw_text")),
        ]
        if part
    ).lower()
    return any(token in compact_item_text for token in query_tokens if len(token) >= 5)


def _fetch_text(url: str, *, source: str = "unknown") -> str:
    response = httpx.get(
        url,
        headers=REQUEST_HEADERS,
        timeout=FETCH_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    try:
        return response.content.decode("utf-8")
    except UnicodeDecodeError:
        pass

    declared = (response.charset_encoding or "").strip()
    if declared and declared.lower().replace("_", "-") != "utf-8":
        try:
            return response.content.decode(declared)
        except (UnicodeDecodeError, LookupError):
            pass

    reason = f"could not decode bytes as utf-8 (declared charset={declared or 'none'})"
    logger.warning(
        "vacancy_source_decode_failed source=%s url=%s declared_charset=%s",
        source,
        url,
        declared or "none",
    )
    raise VacancyFetchError(url=url, source=source, reason=reason)


def _build_hh_headers() -> dict[str, str]:
    headers = dict(REQUEST_HEADERS)
    if settings.hh_api_token:
        headers["Authorization"] = f"Bearer {settings.hh_api_token}"
    return headers


def _hh_get_with_fallback(*, params: dict[str, Any]) -> httpx.Response:
    headers = _build_hh_headers()
    response = httpx.get(HH_PUBLIC_API_URL, params=params, headers=headers, timeout=20)
    if response.status_code == 403 and "Authorization" in headers:
        # Fallback to public API mode when provided token is not accepted for vacancy search endpoint.
        response = httpx.get(HH_PUBLIC_API_URL, params=params, headers=REQUEST_HEADERS, timeout=20)
    return response


def _extract_meta_description(page_html: str) -> str | None:
    patterns = (
        r'<meta\s+name="description"\s+content="([^"]+)"',
        r'<meta\s+property="og:description"\s+content="([^"]+)"',
    )
    for pattern in patterns:
        match = re.search(pattern, page_html, flags=re.IGNORECASE)
        if match:
            return _strip_html(match.group(1))
    return None


def _normalize_hh_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or ""
    vacancy_id_match = re.search(r"/vacancy/(\d+)", path)
    if not vacancy_id_match:
        return url
    vacancy_id = vacancy_id_match.group(1)
    return f"https://hh.ru/vacancy/{vacancy_id}"


def _extract_links(page_html: str, pattern: str) -> list[tuple[str, str]]:
    compiled = re.compile(pattern, flags=re.IGNORECASE | re.DOTALL)
    found: list[tuple[str, str]] = []
    for match in compiled.finditer(page_html):
        href = html.unescape(match.group("href")).strip()
        title = _strip_html(match.group("title"))
        if not href or not title:
            continue
        found.append((href, title))
    return found


def _host_allowed(source_url: str) -> bool:
    host = (urlparse(source_url).hostname or "").lower()
    if not host:
        return False
    if any(host == blocked or host.endswith(f".{blocked}") for blocked in BLOCKED_JOB_HOSTS):
        return False
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in ALLOWED_JOB_HOSTS)


def _collect_public_hh_vacancies(
    *, query: str, count: int, start_page: int = 0
) -> list[dict[str, Any]]:
    vacancies: list[dict[str, Any]] = []
    seen: set[str] = set()
    first_page = max(0, start_page)
    for page in range(first_page, first_page + MAX_PUBLIC_SOURCE_PAGES):
        search_url = (
            "https://hh.ru/search/vacancy"
            f"?text={quote_plus(query)}&area=113&search_field=name&search_field=company_name"
            f"&search_field=description&items_on_page=50&page={page}"
        )
        try:
            page_html = _fetch_text(search_url, source="hh_public")
        except VacancyFetchError as error:
            _record_parse_skip(source=error.source, url=error.url, reason=error.reason)
            continue
        links = _extract_links(
            page_html,
            r'<a[^>]+href="(?P<href>(?:https?://[^"]*hh\.ru)?/vacancy/\d+[^"]*)"[^>]*>(?P<title>.*?)</a>',
        )
        for href, title in links:
            source_url = _normalize_hh_url(urljoin("https://hh.ru", href))
            if source_url in seen:
                continue
            seen.add(source_url)
            vacancies.append(
                {
                    "source": "hh_public",
                    "source_url": source_url,
                    "title": title[:512],
                    "company": None,
                    "location": None,
                    "raw_payload": {"search_url": search_url, "page": page},
                    "raw_text": None,
                }
            )
            if len(vacancies) >= count:
                return vacancies
        if not links:
            break
    return vacancies


def _collect_public_habr_vacancies(
    *, query: str, count: int, start_page: int = 0
) -> list[dict[str, Any]]:
    vacancies: list[dict[str, Any]] = []
    seen: set[str] = set()
    first_page = max(1, start_page + 1)
    for page in range(first_page, first_page + MAX_PUBLIC_SOURCE_PAGES):
        search_url = f"https://career.habr.com/vacancies?q={quote_plus(query)}&page={page}"
        try:
            page_html = _fetch_text(search_url, source="habr_public")
        except VacancyFetchError as error:
            _record_parse_skip(source=error.source, url=error.url, reason=error.reason)
            continue
        links = _extract_links(
            page_html,
            r'<a[^>]+href="(?P<href>/vacancies/\d+[^"]*)"[^>]*>(?P<title>.*?)</a>',
        )
        for href, title in links:
            source_url = urljoin("https://career.habr.com", href)
            if source_url in seen:
                continue
            seen.add(source_url)
            vacancies.append(
                {
                    "source": "habr_public",
                    "source_url": source_url,
                    "title": title[:512],
                    "company": None,
                    "location": None,
                    "raw_payload": {"search_url": search_url, "page": page},
                    "raw_text": None,
                }
            )
            if len(vacancies) >= count:
                return vacancies
        if not links:
            break
    return vacancies


def _collect_public_superjob_vacancies(
    *, query: str, count: int, start_page: int = 0
) -> list[dict[str, Any]]:
    vacancies: list[dict[str, Any]] = []
    seen: set[str] = set()
    first_page = max(1, start_page + 1)
    for page in range(first_page, first_page + MAX_PUBLIC_SOURCE_PAGES):
        search_url = f"https://www.superjob.ru/vakansii/?keywords={quote_plus(query)}&page={page}"
        try:
            page_html = _fetch_text(search_url, source="superjob_public")
        except VacancyFetchError as error:
            _record_parse_skip(source=error.source, url=error.url, reason=error.reason)
            continue
        links = _extract_links(
            page_html,
            r'<a[^>]+href="(?P<href>/vakansii/[^"]+?\.html[^"]*)"[^>]*>(?P<title>.*?)</a>',
        )
        for href, title in links:
            source_url = urljoin("https://www.superjob.ru", href)
            if source_url in seen:
                continue
            seen.add(source_url)
            vacancies.append(
                {
                    "source": "superjob_public",
                    "source_url": source_url,
                    "title": title[:512],
                    "company": None,
                    "location": None,
                    "raw_payload": {"search_url": search_url, "page": page},
                    "raw_text": None,
                }
            )
            if len(vacancies) >= count:
                return vacancies
        if not links:
            break
    return vacancies


def _search_public_sources(*, query: str, count: int, start_page: int = 0) -> list[dict[str, Any]]:
    providers = (
        _collect_public_hh_vacancies,
        _collect_public_habr_vacancies,
        _collect_public_superjob_vacancies,
    )
    source_buckets: list[list[dict[str, Any]]] = []
    for provider in providers:
        try:
            source_buckets.append(
                provider(query=query, count=max(count, 30), start_page=start_page)
            )
        except Exception:
            continue

    aggregated: list[dict[str, Any]] = []
    max_bucket_size = max((len(bucket) for bucket in source_buckets), default=0)
    for index in range(max_bucket_size):
        for bucket in source_buckets:
            if index < len(bucket):
                aggregated.append(bucket[index])

    deduplicated: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for item in aggregated:
        source_url = item.get("source_url")
        if not isinstance(source_url, str):
            continue
        if not _host_allowed(source_url):
            continue
        key = source_url.strip().lower()
        if not key or key in seen_urls:
            continue
        seen_urls.add(key)
        deduplicated.append(item)
        if len(deduplicated) >= count:
            break
    return deduplicated


def _search_superjob_api_vacancies(
    *, query: str, count: int, start_page: int = 0
) -> list[dict[str, Any]]:
    if not settings.superjob_api_key:
        return []

    vacancies: list[dict[str, Any]] = []
    headers = {"X-Api-App-Id": settings.superjob_api_key}
    first_page = max(0, start_page)
    for page in range(first_page, first_page + MAX_API_SOURCE_PAGES):
        params = {"keyword": query, "count": min(max(count, 30), 100), "page": page}
        response = httpx.get(
            settings.superjob_vacancies_url,
            params=params,
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("objects", []) if isinstance(payload, dict) else []
        if not items:
            break

        for item in items:
            if not isinstance(item, dict):
                continue
            title = _to_str(item.get("profession"))
            source_url = _to_str(item.get("link"))
            if not title or not source_url:
                continue

            vacancies.append(
                {
                    "source": "superjob",
                    "source_url": source_url,
                    "title": title[:512],
                    "company": _to_str(item.get("firm_name")),
                    "location": None,
                    "raw_payload": item,
                    "raw_text": _to_str(item.get("candidat")) or _to_str(item.get("work")),
                }
            )
            if len(vacancies) >= count:
                return vacancies
    return vacancies


def _format_hh_date_from(value: datetime) -> str:
    # HH API expects ISO-8601 with timezone offset; naive timestamps are
    # treated as UTC by convention across our pipeline.
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.strftime("%Y-%m-%dT%H:%M:%S%z")


def _fetch_hh_page(
    *, query: str, per_page: int, page: int, date_from: datetime | None
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "text": query,
        "per_page": per_page,
        "page": page,
        "area": settings.hh_area,
        "search_field": ["name", "company_name", "description"],
    }
    if date_from is not None:
        params["date_from"] = _format_hh_date_from(date_from)
    try:
        response = _hh_get_with_fallback(params=params)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = (exc.response.text or "")[:200] if exc.response is not None else ""
        logger.warning(
            "hh_api_http_error status=%s page=%s query=%r body=%s",
            exc.response.status_code if exc.response is not None else "?",
            page,
            query,
            body,
        )
        return []
    except httpx.RequestError as exc:
        logger.warning("hh_api_request_error page=%s query=%r error=%s", page, query, exc)
        return []
    try:
        payload = response.json()
    except ValueError as exc:
        logger.warning("hh_api_json_error page=%s query=%r error=%s", page, query, exc)
        return []
    items = payload.get("items", []) if isinstance(payload, dict) else []
    return items if isinstance(items, list) else []


def _parse_hh_items(
    items: list[dict[str, Any]],
    *,
    vacancies: list[dict[str, Any]],
    seen_urls: set[str],
    count: int,
) -> bool:
    """Append parsed items to `vacancies` in-place. Returns True when full."""
    for item in items:
        if not isinstance(item, dict):
            continue
        title = _to_str(item.get("name"))
        source_url = _to_str(item.get("alternate_url")) or _to_str(item.get("url"))
        if not title or not source_url:
            continue
        source_url = _normalize_hh_url(source_url)
        if source_url in seen_urls:
            continue
        seen_urls.add(source_url)

        employer = item.get("employer")
        area = item.get("area")
        snippet = item.get("snippet")
        company = _to_str(employer.get("name")) if isinstance(employer, dict) else None
        location = _to_str(area.get("name")) if isinstance(area, dict) else None
        requirement = None
        responsibility = None
        if isinstance(snippet, dict):
            requirement = _to_str(snippet.get("requirement"))
            responsibility = _to_str(snippet.get("responsibility"))

        raw_text = "\n".join(
            part for part in [title, company, location, requirement, responsibility] if part
        )

        vacancies.append(
            {
                "source": "hh_api",
                "source_url": source_url,
                "title": title[:512],
                "company": company,
                "location": location,
                "raw_payload": item,
                "raw_text": _strip_html(raw_text) if raw_text else None,
            }
        )
        if len(vacancies) >= count:
            return True
    return False


def _search_hh_public_api_vacancies(
    *,
    query: str,
    count: int,
    start_page: int = 0,
    date_from: datetime | None = None,
    already_indexed_probe: Callable[[list[str]], int] | None = None,
) -> list[dict[str, Any]]:
    vacancies: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    per_page = min(max(count, 30), 100)
    # HH public API caps each search at page * per_page ≤ 2000, so with
    # per_page=100 the hard ceiling is 20 pages. Scale max_pages with the
    # requested count so admin deep scans (count=2000) can actually reach
    # page 19; small user counts keep the old 8-page minimum.
    pages_needed = (count + per_page - 1) // max(1, per_page)
    max_pages = min(20, max(MAX_API_SOURCE_PAGES, 8, pages_needed + 2))
    first_page = max(0, start_page)

    def _should_truncate_by_indexed(page_vacancies: list[dict[str, Any]]) -> bool:
        if already_indexed_probe is None:
            return False
        if len(page_vacancies) < ALREADY_INDEXED_BREAK_MIN_PAGE_SIZE:
            return False
        urls = [str(v["source_url"]) for v in page_vacancies if v.get("source_url")]
        if not urls:
            return False
        try:
            known = int(already_indexed_probe(urls))
        except Exception as exc:  # pragma: no cover — defensive, probe must not break paging
            logger.warning("hh_already_indexed_probe_failed error=%s", exc)
            return False
        ratio = known / len(urls)
        if ratio < ALREADY_INDEXED_BREAK_RATIO:
            return False
        stats = _PARSE_STATS.get()
        if stats is not None:
            stats.record_page_truncated_by_indexed()
        return True

    # Fetch the first HH_CONCURRENCY pages in parallel. In the common case
    # (count=40, per_page=100) the first wave satisfies the request; the
    # sequential fall-through only runs for deep scans.
    wave_size = min(HH_CONCURRENCY, max_pages)
    wave_pages = list(range(first_page, first_page + wave_size))
    page_items: dict[int, list[dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=HH_CONCURRENCY) as pool:
        futures = {
            pool.submit(
                _fetch_hh_page,
                query=query,
                per_page=per_page,
                page=page,
                date_from=date_from,
            ): page
            for page in wave_pages
        }
        for future in as_completed(futures):
            page_num = futures[future]
            try:
                page_items[page_num] = future.result()
            except Exception as exc:
                logger.warning(
                    "hh_api_worker_failed page=%s query=%r error=%s", page_num, query, exc
                )
                page_items[page_num] = []

    last_wave_empty = False
    for page in wave_pages:
        items = page_items.get(page, [])
        if not items:
            last_wave_empty = True
            continue
        last_wave_empty = False
        before_count = len(vacancies)
        full = _parse_hh_items(items, vacancies=vacancies, seen_urls=seen_urls, count=count)
        if full:
            return vacancies
        page_vacancies = vacancies[before_count:]
        if _should_truncate_by_indexed(page_vacancies):
            return vacancies

    # Only continue sequentially if the first wave produced results on its
    # last page — otherwise we've very likely exhausted HH.
    if last_wave_empty or len(vacancies) >= count:
        return vacancies

    for page in range(first_page + wave_size, first_page + max_pages):
        items = _fetch_hh_page(query=query, per_page=per_page, page=page, date_from=date_from)
        if not items:
            break
        before_count = len(vacancies)
        full = _parse_hh_items(items, vacancies=vacancies, seen_urls=seen_urls, count=count)
        if full:
            return vacancies
        page_vacancies = vacancies[before_count:]
        if _should_truncate_by_indexed(page_vacancies):
            return vacancies
    return vacancies


def _search_habr_api_vacancies(
    *, query: str, count: int, start_page: int = 0
) -> list[dict[str, Any]]:
    if not settings.habr_career_api_token:
        return []

    vacancies: list[dict[str, Any]] = []
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.habr_career_api_token}",
    }
    first_page = max(1, start_page + 1)
    for page in range(first_page, first_page + MAX_API_SOURCE_PAGES):
        params = {"q": query, "per_page": min(max(count, 20), 50), "page": page}
        response = httpx.get(
            settings.habr_career_api_url,
            params=params,
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("vacancies", []) if isinstance(payload, dict) else []
        if not items:
            break

        for item in items:
            if not isinstance(item, dict):
                continue
            title = _to_str(item.get("title"))
            source_url = _to_str(item.get("url"))
            if not title or not source_url:
                continue
            vacancies.append(
                {
                    "source": "habr_career",
                    "source_url": source_url,
                    "title": title[:512],
                    "company": None,
                    "location": None,
                    "raw_payload": item,
                    "raw_text": _to_str(item.get("description")),
                }
            )
            if len(vacancies) >= count:
                return vacancies
    return vacancies


def _enrich_preview(vacancies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Keep interactive discovery responsive: skip heavy preview-enrichment on large batches.
    if len(vacancies) > 40:
        return vacancies
    enriched: list[dict[str, Any]] = []
    started_at = time.monotonic()
    attempted = 0
    for item in vacancies:
        source_url = item.get("source_url")
        if not isinstance(source_url, str):
            continue
        has_raw_text = bool(_to_str(item.get("raw_text")))
        within_budget = (time.monotonic() - started_at) <= ENRICH_TIME_BUDGET_SECONDS
        can_attempt = attempted < MAX_PREVIEW_ENRICH and within_budget and not has_raw_text
        if can_attempt:
            attempted += 1
            item_source = _to_str(item.get("source")) or "preview_enrich"
            try:
                detail_html = _fetch_text(source_url, source=item_source)
                description = _extract_meta_description(detail_html)
                if description and not item.get("raw_text"):
                    item["raw_text"] = description
            except VacancyFetchError as error:
                _record_parse_skip(source=error.source, url=error.url, reason=error.reason)
                _record_enrich_fail()
            except Exception:
                _record_enrich_fail()
        enriched.append(item)
    return enriched


def search_vacancies(
    *,
    query: str,
    count: int,
    use_brave_fallback: bool = False,
    page_offset: int = 0,
    date_from: datetime | None = None,
    already_indexed_probe: Callable[[list[str]], int] | None = None,
) -> list[dict[str, Any]]:
    # Temporary strategy: use only HH API as vacancy source.
    # Other sources (Habr/SuperJob/public pages/Brave) are intentionally disabled here.
    _ = use_brave_fallback
    try:
        aggregated = _search_hh_public_api_vacancies(
            query=query,
            count=count,
            start_page=page_offset,
            date_from=date_from,
            already_indexed_probe=already_indexed_probe,
        )
    except Exception as exc:
        logger.warning(
            "hh_search_failed query=%r count=%s page_offset=%s error=%s",
            query,
            count,
            page_offset,
            exc,
        )
        aggregated = []

    parse_stats = _PARSE_STATS.get()
    if parse_stats is not None:
        parse_stats.record_hh_fetched(len(aggregated))

    deduplicated: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for item in aggregated:
        source_url = item.get("source_url")
        if not isinstance(source_url, str):
            continue
        key = source_url.strip().lower()
        if not key or key in seen_urls:
            if parse_stats is not None and key:
                parse_stats.record_dedup()
            continue
        source_name = _to_str(item.get("source")) or ""
        if source_name in STRICT_QUERY_MATCH_SOURCES and not _query_matches_item(query, item):
            if parse_stats is not None:
                parse_stats.record_strict_reject()
            continue
        seen_urls.add(key)
        deduplicated.append(item)
        if len(deduplicated) >= count:
            break

    deduplicated = _enrich_preview(deduplicated)
    if not deduplicated and page_offset > 0:
        return search_vacancies(
            query=query,
            count=count,
            use_brave_fallback=False,
            page_offset=0,
            date_from=date_from,
            already_indexed_probe=already_indexed_probe,
        )
    return deduplicated
