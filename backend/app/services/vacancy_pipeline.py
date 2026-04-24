import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.vacancy import Vacancy
from app.repositories.vacancies import create_vacancy, get_vacancy_by_source_url, update_vacancy
from app.services.openai_usage import OpenAIBudgetExceeded
from app.services.vacancy_analyzer import analyze_vacancy_text
from app.services.vacancy_profile_pipeline import persist_vacancy_profile
from app.services.vacancy_sources import (
    VacancyParseStats,
    search_vacancies,
    vacancy_parse_stats_scope,
)

logger = logging.getLogger(__name__)

# Phase 2.0 PR A2: run LLM analyses concurrently so cold-start discovery
# stops being dominated by 18-40 sequential OpenAI round-trips. Semaphore
# is conservative — OpenAI tier limits + our daily budget guard are the
# actual backpressure mechanism, we just want to hide latency.
LLM_CONCURRENCY = 5

ALLOWED_JOB_HOSTS = (
    "hh.ru",
    "career.habr.com",
    "superjob.ru",
)
BLOCKED_JOB_HOSTS = (
    "djinni.co",
    "workingnomads.com",
)


@dataclass
class VacancyDiscoveryMetrics:
    fetched: int = 0
    prefiltered: int = 0
    analyzed: int = 0
    filtered: int = 0
    indexed: int = 0
    failed: int = 0
    already_indexed_skipped: int = 0
    skipped_parse_errors: int = 0
    sources: list[str] | None = None
    # Funnel observability (Phase 3.2): raw-fetch counters from
    # ``VacancyParseStats`` get copied in at the end of the discovery
    # scope, so the admin waterfall can show drops that happen BEFORE
    # a candidate reaches ``_collect_eligible``.
    hh_fetched_raw: int = 0
    search_dedup_skipped: int = 0
    search_strict_rejected: int = 0
    enrich_failed: int = 0
    # D1: HH pagination stopped early because ≥90% of a page was already
    # in our index. Count of such early-breaks across all queries in one run.
    pages_truncated_by_indexed: int = 0
    # Reason-split of the single ``filtered`` counter — each exclusive.
    filtered_host_not_allowed: int = 0
    filtered_non_rf: int = 0
    filtered_non_vacancy_page: int = 0
    filtered_archived: int = 0
    filtered_listing: int = 0
    filtered_non_vacancy_llm: int = 0
    # Matcher-sourced counters (populated by state.export_to).
    hard_filter_drop_work_format: int = 0
    hard_filter_drop_geo: int = 0
    hard_filter_drop_no_skill_overlap: int = 0
    hard_filter_drop_domain_mismatch: int = 0
    seniority_penalty_applied: int = 0
    archived_at_match_time: int = 0
    title_boost_applied: int = 0
    matcher_runs_total: int = 0
    matcher_recall_count: int = 0
    matcher_drop_listing_page: int = 0
    matcher_drop_non_vacancy_page: int = 0
    matcher_drop_host_not_allowed: int = 0
    matcher_drop_unlikely_stack: int = 0
    matcher_drop_business_role: int = 0
    matcher_drop_hard_non_it: int = 0
    matcher_drop_dedupe: int = 0
    matcher_drop_mmr_dedupe: int = 0
    # Silent-drop counters (Phase v0.9.4): track URLs that vanish before LLM.
    # fetched_dropped_analyzed_budget — items skipped once max_analyzed is hit.
    # fetched_dedup_within_job — same URL seen twice across different queries.
    fetched_dropped_analyzed_budget: int = 0
    fetched_dedup_within_job: int = 0
    cursor_fallback_queries_run: int = 0


@dataclass
class VacancyDiscoveryResult:
    indexed_vacancies: list
    metrics: VacancyDiscoveryMetrics


def _host_allowed_for_matching(source_url: str) -> bool:
    host = (urlparse(source_url).hostname or "").lower()
    if not host:
        return False
    if any(host == blocked or host.endswith(f".{blocked}") for blocked in BLOCKED_JOB_HOSTS):
        return False
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in ALLOWED_JOB_HOSTS)


def _looks_like_listing_page(source_url: str, title: str) -> bool:
    parsed = urlparse(source_url)
    path = (parsed.path or "").lower()
    lowered_title = title.lower().strip()

    if "keyword" in path or "/search" in path or "/vacancies/skills" in path:
        return True
    if lowered_title.startswith("работа ") or " свежих ваканс" in lowered_title:
        return True
    if lowered_title in {"hh", "hh |", "superjob", "habr career"}:
        return True
    if lowered_title in {"vacancies", "jobs", "работа", "вакансии"}:
        return True
    if lowered_title.startswith("jobs ") or lowered_title.startswith("вакансии "):
        return True
    if lowered_title.endswith(" вакансии") or lowered_title.endswith(" vacancies"):
        return True

    has_digit = bool(re.search(r"\d", path))
    has_uuid = bool(
        re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", path)
    )
    if (
        ("/jobs/" in path or "/vacancies/" in path or "/vakansii/" in path)
        and not has_digit
        and not has_uuid
    ):
        return True

    return False


def _looks_archived_vacancy(title: str, raw_text: str | None) -> bool:
    text = f"{title}\n{raw_text or ''}".lower()
    archived_markers = (
        "вакансия в архиве",
        "в архиве",
        "архивная вакансия",
        "vacancy archived",
        "job archived",
        "position archived",
        "no longer accepting",
    )
    return any(marker in text for marker in archived_markers)


def _looks_archived_vacancy_strict(source_url: str, title: str, raw_text: str | None) -> bool:
    text = f"{title}\n{raw_text or ''}\n{source_url}".lower()
    archived_markers = (
        "вакансия в архиве",
        "архивная вакансия",
        "в архиве",
        "вакансия закрыта",
        "вакансия неактуальна",
        "архиве c",
        "архиве с",
        "/archive/",
        "archived",
        "position closed",
        "job closed",
        "vacancy archived",
        "job archived",
        "position archived",
        "no longer accepting",
        "no longer available",
    )
    if any(marker in text for marker in archived_markers):
        return True
    return _looks_archived_vacancy(title, raw_text)


def _looks_non_vacancy_page(source_url: str) -> bool:
    parsed = urlparse(source_url)
    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()

    common_non_vacancy_markers = (
        "/resume/",
        "/resumes/",
        "/candidate/",
        "/candidates/",
        "/profile/",
        "/profiles/",
        "/companies/",
        "/company/",
    )
    if any(marker in path for marker in common_non_vacancy_markers):
        return True

    if "hh.ru" in host:
        return "/vacancy/" not in path
    if "career.habr.com" in host:
        return not path.startswith("/vacancies/")
    if "superjob.ru" in host:
        return "/vakansii/" not in path

    return True


def _looks_like_rf_vacancy(
    source_url: str, title: str, raw_text: str | None, location: str | None
) -> bool:
    hostname = (urlparse(source_url).hostname or "").lower()
    text = f"{title}\n{raw_text or ''}\n{location or ''}".lower()
    rf_markers = (
        "россия",
        "рф",
        "москва",
        "санкт-петербург",
        "spb",
        "екатеринбург",
        "новосибирск",
        "казань",
        "нижний новгород",
        "самара",
        "ростов-на-дону",
        "удаленно по россии",
    )
    if hostname.endswith(".ru"):
        return True
    return any(marker in text for marker in rf_markers)


def _build_vacancy_analysis_input(
    *, title: str, source_url: str, raw_text: str | None, company: str | None
) -> str:
    parts = [
        f"Vacancy title: {title}",
        f"Company: {company or 'unknown'}",
        f"Source URL: {source_url}",
        "Vacancy text:",
        raw_text or "",
    ]
    return "\n".join(parts)


def _build_rotation_offset(query: str, count: int, attempt: int) -> int:
    # Rotate pages between retries to avoid repeatedly taking the same top results.
    # We use a wider offset range so repeated runs can reach deeper unseen pages.
    five_minute_bucket = int(time.time() // 300)
    base = abs(hash((query.lower().strip(), five_minute_bucket))) % 12
    step = max(2, min(20, count // 20))
    return max(1, min(90, base + (attempt * step)))


def discover_and_index_vacancies(
    db: Session,
    *,
    query: str,
    count: int,
    rf_only: bool = True,
    force_reindex: bool = False,
    use_brave_fallback: bool = False,
    max_analyzed: int | None = None,
    date_from: datetime | None = None,
) -> VacancyDiscoveryResult:
    metrics = VacancyDiscoveryMetrics(fetched=0, sources=[])
    indexed = []
    processed_source_urls: set[str] = set()
    stop_processing = False

    def _mark_filtered(vacancy, reason: str, bucket: str) -> None:
        vacancy.status = "filtered"
        vacancy.error_message = reason
        db.add(vacancy)
        db.commit()
        db.refresh(vacancy)
        metrics.prefiltered += 1
        metrics.filtered += 1
        if bucket == "host_not_allowed":
            metrics.filtered_host_not_allowed += 1
        elif bucket == "non_rf":
            metrics.filtered_non_rf += 1
        elif bucket == "non_vacancy_page":
            metrics.filtered_non_vacancy_page += 1
        elif bucket == "archived":
            metrics.filtered_archived += 1
        elif bucket == "listing":
            metrics.filtered_listing += 1

    def _collect_eligible(found_items: list[dict]) -> list[tuple]:
        """Prefilter + upsert rows. Returns (vacancy, analysis_input) ready
        for LLM parse. Stops collecting when the analyzed budget is full."""
        nonlocal metrics, stop_processing
        eligible: list[tuple] = []
        for item in found_items:
            source_url = item["source_url"]
            if stop_processing:
                # Budget exhausted — count unique URLs we are skipping but
                # do NOT increment fetched (they never entered the pipeline).
                if source_url not in processed_source_urls:
                    metrics.fetched_dropped_analyzed_budget += 1
                    processed_source_urls.add(source_url)
                continue
            if source_url in processed_source_urls:
                metrics.fetched_dedup_within_job += 1
                continue
            processed_source_urls.add(source_url)
            metrics.fetched += 1

            if metrics.sources is not None and source_url not in metrics.sources:
                metrics.sources.append(source_url)

            vacancy = None
            try:
                vacancy = get_vacancy_by_source_url(db, source_url=source_url)
                was_existing = vacancy is not None
                if vacancy is None:
                    vacancy = create_vacancy(
                        db,
                        source=item["source"],
                        source_url=source_url,
                        title=item["title"],
                        company=item["company"],
                        location=item["location"],
                        raw_payload=item["raw_payload"],
                        raw_text=item["raw_text"],
                    )
                else:
                    vacancy = update_vacancy(
                        db,
                        vacancy,
                        title=item["title"],
                        company=item["company"],
                        location=item["location"],
                        raw_payload=item["raw_payload"],
                        raw_text=item["raw_text"],
                        status="indexed",
                        error_message=None,
                    )

                has_profile = vacancy.profile is not None
                if (
                    was_existing
                    and not force_reindex
                    and vacancy.status == "indexed"
                    and has_profile
                ):
                    metrics.already_indexed_skipped += 1
                    continue

                if not _host_allowed_for_matching(vacancy.source_url):
                    _mark_filtered(vacancy, "Filtered as non-target source", "host_not_allowed")
                    continue
                if rf_only and not _looks_like_rf_vacancy(
                    vacancy.source_url, vacancy.title, vacancy.raw_text, vacancy.location
                ):
                    _mark_filtered(vacancy, "Filtered as non-RF vacancy", "non_rf")
                    continue
                if _looks_non_vacancy_page(vacancy.source_url):
                    _mark_filtered(vacancy, "Filtered as non-vacancy page", "non_vacancy_page")
                    continue
                if _looks_archived_vacancy_strict(
                    vacancy.source_url, vacancy.title, vacancy.raw_text
                ):
                    _mark_filtered(vacancy, "Filtered as archived vacancy", "archived")
                    continue
                if _looks_like_listing_page(vacancy.source_url, vacancy.title):
                    _mark_filtered(vacancy, "Filtered as listing/aggregator page", "listing")
                    continue

                if max_analyzed is not None and metrics.analyzed + len(eligible) >= max_analyzed:
                    stop_processing = True
                    # This item already incremented metrics.fetched above so we
                    # do NOT also count it as dropped.  Use continue (not break)
                    # so the remaining items in found_items are iterated and
                    # counted via the stop_processing branch at the loop top.
                    continue

                analysis_input = _build_vacancy_analysis_input(
                    title=vacancy.title,
                    source_url=vacancy.source_url,
                    raw_text=vacancy.raw_text,
                    company=vacancy.company,
                )
                eligible.append((vacancy, analysis_input))
            except Exception as error:
                if vacancy is not None:
                    vacancy.status = "failed"
                    vacancy.error_message = str(error)
                    db.add(vacancy)
                    db.commit()
                    db.refresh(vacancy)
                metrics.failed += 1
        return eligible

    def _analyze_parallel(pending: list[tuple]) -> list[tuple]:
        """Run analyze_vacancy_text across threads. DB is untouched inside
        worker threads — only the pure OpenAI call runs there. Returns
        (vacancy, profile_or_None, error_or_None) in original submission
        order. Re-raises OpenAIBudgetExceeded after cancelling siblings."""
        if not pending:
            return []
        results: dict[int, tuple] = {}
        workers = min(LLM_CONCURRENCY, len(pending))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="llm-parse") as pool:
            future_to_idx = {
                pool.submit(analyze_vacancy_text, inp): idx for idx, (_, inp) in enumerate(pending)
            }
            budget_error: OpenAIBudgetExceeded | None = None
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                vacancy, _ = pending[idx]
                try:
                    profile = future.result()
                    results[idx] = (vacancy, profile, None)
                except OpenAIBudgetExceeded as err:
                    # Capture and cancel the rest; re-raise once the pool drains.
                    budget_error = err
                    for pending_future in future_to_idx:
                        if not pending_future.done():
                            pending_future.cancel()
                    results[idx] = (vacancy, None, err)
                except Exception as err:
                    results[idx] = (vacancy, None, err)
        if budget_error is not None:
            raise budget_error
        return [results[i] for i in sorted(results)]

    def _persist_analysis(analyzed: list[tuple]) -> None:
        """Serialized DB writes for the LLM results. Threads are done by now."""
        nonlocal metrics, indexed
        for vacancy, profile, error in analyzed:
            metrics.analyzed += 1
            if error is not None:
                if vacancy is not None:
                    vacancy.status = "failed"
                    vacancy.error_message = str(error)
                    db.add(vacancy)
                    db.commit()
                    db.refresh(vacancy)
                metrics.failed += 1
                continue
            try:
                is_vacancy = bool(profile.get("is_vacancy"))
                confidence = float(profile.get("vacancy_confidence") or 0.0)
                if not is_vacancy or confidence < 0.55:
                    rejection_reason = (
                        profile.get("rejection_reason") or "Filtered as non-vacancy content"
                    )
                    vacancy.status = "filtered"
                    vacancy.error_message = str(rejection_reason)
                    db.add(vacancy)
                    db.commit()
                    db.refresh(vacancy)
                    metrics.filtered += 1
                    metrics.filtered_non_vacancy_llm += 1
                    continue
                persist_vacancy_profile(
                    db,
                    vacancy_id=vacancy.id,
                    source_url=vacancy.source_url,
                    title=vacancy.title,
                    company=vacancy.company,
                    profile=profile,
                )
                vacancy.status = "indexed"
                vacancy.error_message = None
                db.add(vacancy)
                db.commit()
                db.refresh(vacancy)
                indexed.append(vacancy)
                metrics.indexed += 1
            except Exception as persist_err:
                vacancy.status = "failed"
                vacancy.error_message = str(persist_err)
                db.add(vacancy)
                db.commit()
                db.refresh(vacancy)
                metrics.failed += 1

    def process_items(found_items: list[dict]) -> None:
        pending_analysis = _collect_eligible(found_items)
        analyzed = _analyze_parallel(pending_analysis)
        _persist_analysis(analyzed)

    def _already_indexed_probe(urls: list[str]) -> int:
        """Bulk-count how many of ``urls`` are already stored as indexed
        vacancies. Used by HH pagination to stop fetching once a page
        crosses the saturation threshold."""
        if not urls:
            return 0
        try:
            rows = db.execute(
                select(Vacancy.source_url).where(
                    Vacancy.source_url.in_(urls),
                    Vacancy.status == "indexed",
                )
            ).all()
        except Exception:
            return 0
        return len(rows)

    parse_stats = VacancyParseStats()
    with vacancy_parse_stats_scope(parse_stats):
        first_pass_items = search_vacancies(
            query=query,
            count=count,
            use_brave_fallback=use_brave_fallback,
            page_offset=0,
            date_from=date_from,
            already_indexed_probe=_already_indexed_probe,
        )
        process_items(first_pass_items)

        # Phase 1.9 PR A1: trigger retry whenever the first pass barely
        # indexed anything fresh, not only when it indexed literally zero.
        # The previous `indexed==0 AND analyzed==0` guard never fired when
        # we pulled 2-3 new items but still missed the freshness target,
        # so users saw the same ~40 top results repeatedly.
        if not force_reindex and metrics.indexed < 5:
            expanded_count = min(max(count * 4, 120), 500)
            for attempt in range(1, 7):
                second_pass_items = search_vacancies(
                    query=query,
                    count=expanded_count,
                    use_brave_fallback=use_brave_fallback,
                    page_offset=_build_rotation_offset(
                        query=query, count=expanded_count, attempt=attempt
                    ),
                    date_from=date_from,
                    already_indexed_probe=_already_indexed_probe,
                )
                process_items(second_pass_items)
                if metrics.indexed >= 5:
                    break

    metrics.skipped_parse_errors = parse_stats.skipped_parse_errors
    metrics.hh_fetched_raw = parse_stats.hh_fetched_raw
    metrics.search_dedup_skipped = parse_stats.search_dedup_skipped
    metrics.search_strict_rejected = parse_stats.search_strict_rejected
    metrics.enrich_failed = parse_stats.enrich_failed
    metrics.pages_truncated_by_indexed = parse_stats.pages_truncated_by_indexed
    return VacancyDiscoveryResult(indexed_vacancies=indexed, metrics=metrics)
