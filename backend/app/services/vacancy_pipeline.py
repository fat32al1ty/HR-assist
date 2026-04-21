import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.repositories.vacancies import create_vacancy, get_vacancy_by_source_url, update_vacancy
from app.services.openai_usage import OpenAIBudgetExceeded
from app.services.vacancy_analyzer import analyze_vacancy_text
from app.services.vacancy_profile_pipeline import persist_vacancy_profile
from app.services.vacancy_sources import (
    VacancyParseStats,
    search_vacancies,
    vacancy_parse_stats_scope,
)

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
    hard_filter_drop_work_format: int = 0
    hard_filter_drop_geo: int = 0
    hard_filter_drop_no_skill_overlap: int = 0
    seniority_penalty_applied: int = 0
    archived_at_match_time: int = 0
    title_boost_applied: int = 0


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
) -> VacancyDiscoveryResult:
    metrics = VacancyDiscoveryMetrics(fetched=0, sources=[])
    indexed = []
    processed_source_urls: set[str] = set()
    stop_processing = False

    def process_items(found_items: list[dict]) -> None:
        nonlocal metrics, indexed, stop_processing

        for item in found_items:
            if stop_processing:
                break
            source_url = item["source_url"]
            if source_url in processed_source_urls:
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
                    vacancy.status = "filtered"
                    vacancy.error_message = "Filtered as non-target source"
                    db.add(vacancy)
                    db.commit()
                    db.refresh(vacancy)
                    metrics.prefiltered += 1
                    metrics.filtered += 1
                    continue

                if rf_only and not _looks_like_rf_vacancy(
                    vacancy.source_url, vacancy.title, vacancy.raw_text, vacancy.location
                ):
                    vacancy.status = "filtered"
                    vacancy.error_message = "Filtered as non-RF vacancy"
                    db.add(vacancy)
                    db.commit()
                    db.refresh(vacancy)
                    metrics.prefiltered += 1
                    metrics.filtered += 1
                    continue

                if _looks_non_vacancy_page(vacancy.source_url):
                    vacancy.status = "filtered"
                    vacancy.error_message = "Filtered as non-vacancy page"
                    db.add(vacancy)
                    db.commit()
                    db.refresh(vacancy)
                    metrics.prefiltered += 1
                    metrics.filtered += 1
                    continue

                if _looks_archived_vacancy_strict(
                    vacancy.source_url, vacancy.title, vacancy.raw_text
                ):
                    vacancy.status = "filtered"
                    vacancy.error_message = "Filtered as archived vacancy"
                    db.add(vacancy)
                    db.commit()
                    db.refresh(vacancy)
                    metrics.prefiltered += 1
                    metrics.filtered += 1
                    continue

                if _looks_like_listing_page(vacancy.source_url, vacancy.title):
                    vacancy.status = "filtered"
                    vacancy.error_message = "Filtered as listing/aggregator page"
                    db.add(vacancy)
                    db.commit()
                    db.refresh(vacancy)
                    metrics.prefiltered += 1
                    metrics.filtered += 1
                    continue

                if max_analyzed is not None and metrics.analyzed >= max_analyzed:
                    stop_processing = True
                    break

                metrics.analyzed += 1
                analysis_input = _build_vacancy_analysis_input(
                    title=vacancy.title,
                    source_url=vacancy.source_url,
                    raw_text=vacancy.raw_text,
                    company=vacancy.company,
                )
                profile = analyze_vacancy_text(analysis_input)
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
            except OpenAIBudgetExceeded:
                raise
            except Exception as error:
                if vacancy is not None:
                    vacancy.status = "failed"
                    vacancy.error_message = str(error)
                    db.add(vacancy)
                    db.commit()
                    db.refresh(vacancy)
                metrics.failed += 1

    parse_stats = VacancyParseStats()
    with vacancy_parse_stats_scope(parse_stats):
        first_pass_items = search_vacancies(
            query=query,
            count=count,
            use_brave_fallback=use_brave_fallback,
            page_offset=0,
        )
        process_items(first_pass_items)

        if (
            not force_reindex
            and metrics.indexed == 0
            and metrics.analyzed == 0
            and metrics.already_indexed_skipped > 0
        ):
            expanded_count = min(max(count * 4, 120), 500)
            for attempt in range(1, 7):
                second_pass_items = search_vacancies(
                    query=query,
                    count=expanded_count,
                    use_brave_fallback=use_brave_fallback,
                    page_offset=_build_rotation_offset(
                        query=query, count=expanded_count, attempt=attempt
                    ),
                )
                process_items(second_pass_items)
                if metrics.indexed > 0 or metrics.analyzed > 0:
                    break

    metrics.skipped_parse_errors = parse_stats.skipped_parse_errors
    return VacancyDiscoveryResult(indexed_vacancies=indexed, metrics=metrics)
