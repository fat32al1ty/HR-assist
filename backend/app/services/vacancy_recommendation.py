import re
import time
from collections.abc import Callable
from dataclasses import asdict

from sqlalchemy.orm import Session

from app.repositories.resumes import get_resume_for_user
from app.services.matching_service import match_vacancies_for_resume
from app.services.vacancy_pipeline import VacancyDiscoveryMetrics, discover_and_index_vacancies

MAX_DEEP_SCAN_QUERIES = 6
MAX_TOTAL_DISCOVERY_BUDGET = 140
MAX_TOTAL_ANALYZED_BUDGET = 18
INTERACTIVE_MAX_DEEP_QUERIES = 3
HIGH_QUALITY_MATCH_THRESHOLD = 0.55


def _as_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text:
                result.append(text)
    return result


def _dedupe(items: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = item.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(item)
    return unique


def _normalize_phrase(value: object) -> str:
    if not isinstance(value, str):
        return ""
    normalized = value.replace("/", " ").replace("|", " ").replace("\\", " ")
    normalized = re.sub(r"[^0-9a-zA-Zа-яА-ЯёЁ+\s]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _short_query_from_tokens(tokens: list[str], *, max_words: int = 7) -> str:
    words: list[str] = []
    for token in tokens:
        normalized = _normalize_phrase(token)
        if not normalized:
            continue
        for word in normalized.split():
            if len(words) >= max_words:
                break
            words.append(word)
        if len(words) >= max_words:
            break
    return " ".join(words).strip()


def _build_discovery_query(analysis: dict | None) -> str:
    if not analysis:
        return "python backend developer remote"

    role = _normalize_phrase(analysis.get("target_role"))
    specialization = _normalize_phrase(analysis.get("specialization"))
    keywords = _as_strings(analysis.get("matching_keywords"))
    hard_skills = _as_strings(analysis.get("hard_skills"))

    parts: list[str] = []
    if role:
        parts.append(role)
    if specialization:
        parts.append(specialization)
    parts.extend(_normalize_phrase(item) for item in keywords[:4])
    parts.extend(_normalize_phrase(item) for item in hard_skills[:4])

    compact = _dedupe([item for item in parts if item])
    short = _short_query_from_tokens(compact, max_words=7)
    if not short:
        return "python backend developer remote"
    return short


def _build_deep_scan_queries(base_query: str, rf_only: bool, analysis: dict | None) -> list[str]:
    region_suffix = " Russia" if rf_only else ""
    role = _normalize_phrase(analysis.get("target_role")) if isinstance(analysis, dict) else ""
    specialization = _normalize_phrase(analysis.get("specialization")) if isinstance(analysis, dict) else ""
    keywords = _as_strings(analysis.get("matching_keywords")) if isinstance(analysis, dict) else []
    hard_skills = _as_strings(analysis.get("hard_skills")) if isinstance(analysis, dict) else []
    skill_focus = _short_query_from_tokens(keywords + hard_skills, max_words=6)

    templates = [
        "{q}",
        "{role}",
        "{spec}",
        "{skills}",
        "{q} remote",
        "{q} hybrid",
        "{q} full time",
        "{q} backend",
    ]
    queries: list[str] = []
    for template in templates:
        candidate = (
            template.format(
                q=base_query,
                role=role or base_query,
                spec=specialization or base_query,
                skills=skill_focus or base_query,
            )
            .strip()
        )
        if not candidate:
            continue
        queries.append((candidate + region_suffix).strip())

    role_tokens = _normalize_phrase(role).lower()
    prefers_leadership = any(token in role_tokens for token in ("руководитель", "head", "lead", "manager", "директор"))
    has_observability_intent = any(
        token in f"{role_tokens} {_normalize_phrase(specialization).lower()} {' '.join(x.lower() for x in keywords)}"
        for token in ("observability", "monitoring", "мониторинг", "монитор")
    )
    priority_queries: list[str] = []
    if prefers_leadership:
        leadership_queries = [
            "руководитель мониторинга",
            "head of observability",
            "sre lead",
            "platform engineering manager",
        ]
        if has_observability_intent:
            leadership_queries.extend(
                [
                    "руководитель observability",
                    "руководитель sre",
                    "lead observability engineer",
                ]
            )
        for item in leadership_queries:
            priority_queries.append((item + region_suffix).strip())
    ordered = priority_queries + queries
    return _dedupe([query.strip() for query in ordered if query.strip()])


def _count_high_quality_matches(matches: list[dict], *, threshold: float = HIGH_QUALITY_MATCH_THRESHOLD) -> int:
    count = 0
    for item in matches:
        score = item.get("similarity_score")
        try:
            value = float(score)
        except (TypeError, ValueError):
            continue
        if value >= threshold:
            count += 1
    return count


def _empty_metrics() -> VacancyDiscoveryMetrics:
    return VacancyDiscoveryMetrics(
        fetched=0,
        prefiltered=0,
        analyzed=0,
        filtered=0,
        indexed=0,
        failed=0,
        already_indexed_skipped=0,
        sources=[],
    )


def _merge_metrics(target: VacancyDiscoveryMetrics, current: VacancyDiscoveryMetrics) -> VacancyDiscoveryMetrics:
    target.fetched += current.fetched
    target.prefiltered += current.prefiltered
    target.analyzed += current.analyzed
    target.filtered += current.filtered
    target.indexed += current.indexed
    target.failed += current.failed
    target.already_indexed_skipped += current.already_indexed_skipped
    if target.sources is None:
        target.sources = []
    for source_url in current.sources or []:
        if source_url not in target.sources:
            target.sources.append(source_url)
    return target


def recommend_vacancies_for_resume(
    db: Session,
    *,
    resume_id: int,
    user_id: int,
    discover_count: int = 40,
    match_limit: int = 20,
    deep_scan: bool = True,
    rf_only: bool = True,
    use_brave_fallback: bool = False,
    use_prefetched_index: bool = True,
    discover_if_few_matches: bool = True,
    min_prefetched_matches: int = 8,
    progress_callback: Callable[[str, int, dict | None], None] | None = None,
    max_runtime_seconds: int | None = None,
) -> tuple[str, VacancyDiscoveryMetrics, list[dict]]:
    last_progress = 0
    started_at = time.monotonic()

    def report(stage: str, progress: int, metrics: VacancyDiscoveryMetrics | None = None) -> None:
        nonlocal last_progress
        normalized = max(last_progress, max(0, min(100, progress)))
        last_progress = normalized
        if progress_callback is not None:
            progress_callback(stage, normalized, asdict(metrics) if metrics is not None else None)

    resume = get_resume_for_user(db, resume_id=resume_id, user_id=user_id)
    if resume is None:
        return "", VacancyDiscoveryMetrics(), []

    query = _build_discovery_query(resume.analysis)
    aggregate_metrics = _empty_metrics()
    report("collecting", 5, aggregate_metrics)

    if use_prefetched_index:
        report("matching", 45, aggregate_metrics)
        prefetched_matches = match_vacancies_for_resume(db, resume_id=resume_id, user_id=user_id, limit=match_limit)
        target_match_count = max(1, min(match_limit, min_prefetched_matches))
        enough_prefetched = (
            len(prefetched_matches) >= target_match_count
            and _count_high_quality_matches(prefetched_matches) >= target_match_count
        )
        if enough_prefetched or not discover_if_few_matches:
            report("finalizing", 95, aggregate_metrics)
            return query, aggregate_metrics, prefetched_matches
        report("collecting", 50, aggregate_metrics)
    else:
        target_match_count = max(1, min(match_limit, min_prefetched_matches))
    if deep_scan:
        max_queries = MAX_DEEP_SCAN_QUERIES
        if use_prefetched_index:
            # Interactive UI flow: keep deep scan bounded and return faster.
            max_queries = min(max_queries, INTERACTIVE_MAX_DEEP_QUERIES)
        queries = _build_deep_scan_queries(query, rf_only=rf_only, analysis=resume.analysis)[:max_queries]
        total_budget = min(max(discover_count * len(queries), discover_count), MAX_TOTAL_DISCOVERY_BUDGET)
        per_query_count = max(10, min(40, total_budget // max(1, len(queries))))
        collect_start = 55 if use_prefetched_index else 10
        collect_span = 25 if use_prefetched_index else 60
        for index, deep_query in enumerate(queries):
            if max_runtime_seconds is not None:
                elapsed = time.monotonic() - started_at
                if elapsed >= max_runtime_seconds:
                    break
            report(
                "collecting",
                min(80, collect_start + int((index / max(1, len(queries))) * collect_span)),
                aggregate_metrics,
            )
            remaining_analyzed_budget = max(0, MAX_TOTAL_ANALYZED_BUDGET - aggregate_metrics.analyzed)
            if remaining_analyzed_budget <= 0:
                break
            result = discover_and_index_vacancies(
                db,
                query=deep_query,
                count=per_query_count,
                rf_only=rf_only,
                force_reindex=False,
                use_brave_fallback=use_brave_fallback,
                max_analyzed=remaining_analyzed_budget,
            )
            aggregate_metrics = _merge_metrics(aggregate_metrics, result.metrics)
            report(
                "collecting",
                min(80, collect_start + int(((index + 1) / max(1, len(queries))) * collect_span)),
                aggregate_metrics,
            )
            if use_prefetched_index:
                interim_matches = match_vacancies_for_resume(db, resume_id=resume_id, user_id=user_id, limit=match_limit)
                if (
                    len(interim_matches) >= target_match_count
                    and _count_high_quality_matches(interim_matches) >= target_match_count
                ):
                    report("matching", 85, aggregate_metrics)
                    report("finalizing", 95, aggregate_metrics)
                    return query, aggregate_metrics, interim_matches
            # Stop wasting time if repeated scans only revisit already-indexed links.
            if (
                index >= 1
                and int(result.metrics.analyzed or 0) == 0
                and int(result.metrics.indexed or 0) == 0
                and int(result.metrics.already_indexed_skipped or 0) > 0
            ):
                break
    else:
        if max_runtime_seconds is not None:
            elapsed = time.monotonic() - started_at
            if elapsed >= max_runtime_seconds:
                report("matching", 85, aggregate_metrics)
                matches = match_vacancies_for_resume(db, resume_id=resume_id, user_id=user_id, limit=match_limit)
                report("finalizing", 95, aggregate_metrics)
                return query, aggregate_metrics, matches
        result = discover_and_index_vacancies(
            db,
            query=query,
            count=discover_count,
            rf_only=rf_only,
            force_reindex=False,
            use_brave_fallback=use_brave_fallback,
            max_analyzed=MAX_TOTAL_ANALYZED_BUDGET,
        )
        aggregate_metrics = _merge_metrics(aggregate_metrics, result.metrics)
        report("collecting", 70, aggregate_metrics)

    report("matching", 85, aggregate_metrics)
    matches = match_vacancies_for_resume(db, resume_id=resume_id, user_id=user_id, limit=match_limit)
    report("finalizing", 95, aggregate_metrics)
    return query, aggregate_metrics, matches
