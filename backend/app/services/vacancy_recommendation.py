import re
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.resumes import get_resume_for_user
from app.services.matching_service import match_vacancies_for_resume
from app.services.vacancy_pipeline import VacancyDiscoveryMetrics, discover_and_index_vacancies

MAX_DEEP_SCAN_QUERIES = 6
# Phase 2.1: widen the HTTP scan budget 200→400. HH pagination is free (no
# OpenAI cost) so a bigger scan lets a senior / nichey resume reach into
# page 2-3 of HH where its real matches live. The LLM cap (COLD_START /
# WARM) is unchanged — only items we decide to actually parse spend money.
# MAX_TOTAL_DISCOVERY_BUDGET caps total items across all deep-scan queries
# in one user-initiated recommend; per-query count is derived from it.
MAX_SOURCES_SCANNED = 400
MAX_TOTAL_DISCOVERY_BUDGET = MAX_SOURCES_SCANNED
# Phase 2.0 PR A1: spend more LLM budget on cold-start so first-run users
# actually see results. Warm runs (cursor already populated) keep the
# tight cap — the index is already seeded and further LLM parses mostly
# overlap with existing vectors.
COLD_START_MAX_OPENAI_ANALYZED = 40
WARM_MAX_OPENAI_ANALYZED = 18
MAX_OPENAI_ANALYZED = WARM_MAX_OPENAI_ANALYZED
# Admin override — admins ask for as much as HH will return and as much
# LLM analysis as the per-request/per-user OpenAI budget allows. HH's
# public API hard-caps each search query at ~2000 items (page*per_page
# ≤ 2000 with per_page ≤ 100), so we use 2000 per query and up to 6
# queries. The analyzed cap is a safety-net only — the real brake is
# `openai_request_budget_usd` + `openai_user_daily_budget_usd`.
ADMIN_MAX_SOURCES_SCANNED = 3000
ADMIN_PER_QUERY_CAP = 2000
ADMIN_MAX_OPENAI_ANALYZED = 1000
# Overlap window to tolerate HH's eventual-consistency on new postings —
# a vacancy posted right before our cursor might not be visible yet.
HH_CURSOR_OVERLAP = timedelta(hours=6)
INTERACTIVE_MAX_DEEP_QUERIES = 3
HIGH_QUALITY_MATCH_THRESHOLD = 0.55


def _resolve_scan_budgets(user: User | None, *, is_cold_start: bool) -> tuple[int, int, int, int]:
    """Return (analyzed_budget, sources_scanned_budget, per_query_cap, max_queries).

    Admin accounts (``user.is_admin``) get the wider caps so operators can
    burn through as much of HH's public API and the per-request OpenAI
    budget as possible when profiling the full funnel. Everyone else keeps
    the conservative caps tuned for interactive latency and per-user cost.
    """
    if user is not None and getattr(user, "is_admin", False):
        return (
            ADMIN_MAX_OPENAI_ANALYZED,
            ADMIN_MAX_SOURCES_SCANNED,
            ADMIN_PER_QUERY_CAP,
            MAX_DEEP_SCAN_QUERIES,
        )
    analyzed_budget = COLD_START_MAX_OPENAI_ANALYZED if is_cold_start else WARM_MAX_OPENAI_ANALYZED
    return analyzed_budget, MAX_SOURCES_SCANNED, 150, MAX_DEEP_SCAN_QUERIES


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
    specialization = (
        _normalize_phrase(analysis.get("specialization")) if isinstance(analysis, dict) else ""
    )
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
        candidate = template.format(
            q=base_query,
            role=role or base_query,
            spec=specialization or base_query,
            skills=skill_focus or base_query,
        ).strip()
        if not candidate:
            continue
        queries.append((candidate + region_suffix).strip())

    role_tokens = _normalize_phrase(role).lower()
    prefers_leadership = any(
        token in role_tokens for token in ("руководитель", "head", "lead", "manager", "директор")
    )
    has_observability_intent = any(
        token
        in f"{role_tokens} {_normalize_phrase(specialization).lower()} {' '.join(x.lower() for x in keywords)}"
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


def _count_high_quality_matches(
    matches: list[dict], *, threshold: float = HIGH_QUALITY_MATCH_THRESHOLD
) -> int:
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
    return VacancyDiscoveryMetrics(sources=[])


_METRIC_INT_FIELDS = (
    "fetched",
    "prefiltered",
    "analyzed",
    "filtered",
    "indexed",
    "failed",
    "already_indexed_skipped",
    "skipped_parse_errors",
    "hh_fetched_raw",
    "search_dedup_skipped",
    "search_strict_rejected",
    "enrich_failed",
    "filtered_host_not_allowed",
    "filtered_non_rf",
    "filtered_non_vacancy_page",
    "filtered_archived",
    "filtered_listing",
    "filtered_non_vacancy_llm",
    "pages_truncated_by_indexed",
    "hard_filter_drop_work_format",
    "hard_filter_drop_geo",
    "hard_filter_drop_no_skill_overlap",
    "hard_filter_drop_domain_mismatch",
    "seniority_penalty_applied",
    "archived_at_match_time",
    "title_boost_applied",
    "matcher_runs_total",
    "matcher_recall_count",
    "matcher_drop_listing_page",
    "matcher_drop_non_vacancy_page",
    "matcher_drop_host_not_allowed",
    "matcher_drop_unlikely_stack",
    "matcher_drop_business_role",
    "matcher_drop_hard_non_it",
    "matcher_drop_dedupe",
    "matcher_drop_mmr_dedupe",
)


def _merge_metrics(
    target: VacancyDiscoveryMetrics, current: VacancyDiscoveryMetrics
) -> VacancyDiscoveryMetrics:
    for name in _METRIC_INT_FIELDS:
        setattr(target, name, getattr(target, name) + getattr(current, name))
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
    preference_overrides: dict | None = None,
) -> tuple[str, VacancyDiscoveryMetrics, list[dict]]:
    last_progress = 0
    started_at = time.monotonic()
    matching_metrics: dict[str, int] = {}

    _matcher_metric_to_field = {
        "hard_filter_drop_work_format": "hard_filter_drop_work_format",
        "hard_filter_drop_geo": "hard_filter_drop_geo",
        "hard_filter_drop_no_skill_overlap": "hard_filter_drop_no_skill_overlap",
        "hard_filter_drop_domain_mismatch": "hard_filter_drop_domain_mismatch",
        "seniority_penalty_applied": "seniority_penalty_applied",
        "archived_at_match_time": "archived_at_match_time",
        "title_boost_applied": "title_boost_applied",
        "matcher_runs_total": "matcher_runs_total",
        "matcher_recall_count": "matcher_recall_count",
        "matcher_drop_listing_page": "matcher_drop_listing_page",
        "matcher_drop_non_vacancy_page": "matcher_drop_non_vacancy_page",
        "matcher_drop_host_not_allowed": "matcher_drop_host_not_allowed",
        "matcher_drop_unlikely_stack": "matcher_drop_unlikely_stack",
        "matcher_drop_business_role": "matcher_drop_business_role",
        "matcher_drop_hard_non_it": "matcher_drop_hard_non_it",
        "matcher_drop_dedupe": "matcher_drop_dedupe",
        "matcher_drop_mmr_dedupe": "matcher_drop_mmr_dedupe",
    }

    def _run_matcher(limit: int) -> list[dict]:
        # Wrapper around ``match_vacancies_for_resume`` that bumps the run
        # counter before each call. The matcher itself uses ``metrics.get``
        # + add for its own drops (see ``state.export_to``), so interim
        # runs during one deep-scan sweep stay visible in the final
        # snapshot instead of being overwritten by the last run.
        matching_metrics["matcher_runs_total"] = matching_metrics.get("matcher_runs_total", 0) + 1
        return match_vacancies_for_resume(
            db,
            resume_id=resume_id,
            user_id=user_id,
            limit=limit,
            preference_overrides=preference_overrides,
            metrics=matching_metrics,
        )

    def _absorb_matching_metrics(target: VacancyDiscoveryMetrics) -> VacancyDiscoveryMetrics:
        # The matcher's accumulators live in ``matching_metrics`` and are
        # updated on every run via state.export_to's ``get+`` pattern, so
        # a single read here gives the cumulative counters for the whole
        # ``recommend_vacancies_for_resume`` call.
        for metric_key, field_name in _matcher_metric_to_field.items():
            setattr(target, field_name, int(matching_metrics.get(metric_key, 0) or 0))
        return target

    def report(stage: str, progress: int, metrics: VacancyDiscoveryMetrics | None = None) -> None:
        nonlocal last_progress
        normalized = max(last_progress, max(0, min(100, progress)))
        last_progress = normalized
        if progress_callback is not None:
            progress_callback(stage, normalized, asdict(metrics) if metrics is not None else None)

    resume = get_resume_for_user(db, resume_id=resume_id, user_id=user_id)
    if resume is None:
        return "", VacancyDiscoveryMetrics(), []

    user = db.get(User, user_id)
    cursor_from: datetime | None = None
    if user is not None and user.last_hh_seen_at is not None:
        cursor_from = user.last_hh_seen_at - HH_CURSOR_OVERLAP
    fetch_started_at = datetime.now(UTC)

    is_cold_start = user is None or user.last_hh_seen_at is None
    analyzed_budget, sources_scanned_budget, per_query_cap, admin_max_queries = (
        _resolve_scan_budgets(user, is_cold_start=is_cold_start)
    )
    is_admin = user is not None and bool(getattr(user, "is_admin", False))

    def _commit_cursor() -> None:
        # Only advance the cursor when we actually hit HH on this call.
        # Prefetched-index-only returns do not see newer data, so keeping
        # the old cursor means the next call will still look backwards far
        # enough to find anything posted since the last true fetch.
        if not fetch_succeeded or user is None:
            return
        user.last_hh_seen_at = fetch_started_at
        db.add(user)
        db.commit()

    query = _build_discovery_query(resume.analysis)
    aggregate_metrics = _empty_metrics()
    fetch_succeeded = False
    report("collecting", 5, aggregate_metrics)

    if use_prefetched_index:
        report("matching", 45, aggregate_metrics)
        prefetched_matches = _run_matcher(match_limit)
        target_match_count = max(1, min(match_limit, min_prefetched_matches))
        enough_prefetched = (
            len(prefetched_matches) >= target_match_count
            and _count_high_quality_matches(prefetched_matches) >= target_match_count
        )
        if enough_prefetched or not discover_if_few_matches:
            report("finalizing", 95, aggregate_metrics)
            return query, _absorb_matching_metrics(aggregate_metrics), prefetched_matches
        report("collecting", 50, aggregate_metrics)
    else:
        target_match_count = max(1, min(match_limit, min_prefetched_matches))
    if deep_scan:
        max_queries = admin_max_queries if is_admin else MAX_DEEP_SCAN_QUERIES
        if use_prefetched_index and not is_admin:
            # Interactive UI flow: keep deep scan bounded and return faster.
            # Admins explicitly want maximum coverage, so they skip this cap.
            max_queries = min(max_queries, INTERACTIVE_MAX_DEEP_QUERIES)
        queries = _build_deep_scan_queries(query, rf_only=rf_only, analysis=resume.analysis)[
            :max_queries
        ]
        # Phase 2.1: HH pagination is free; a wider scan lets nichey / senior
        # resumes reach their real matches on page 2-3. Use sources_scanned_budget
        # as the upper bound regardless of discover_count, and raise the
        # per-query cap so pagination can actually go deep. LLM budget is
        # separately capped by analyzed_budget — a bigger scan doesn't spend
        # more OpenAI, just finds more candidates to choose from.
        total_budget = min(
            max(discover_count * len(queries), sources_scanned_budget), sources_scanned_budget
        )
        per_query_count = max(10, min(per_query_cap, total_budget // max(1, len(queries))))
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
            remaining_analyzed_budget = max(0, analyzed_budget - aggregate_metrics.analyzed)
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
                date_from=cursor_from,
            )
            fetch_succeeded = True
            aggregate_metrics = _merge_metrics(aggregate_metrics, result.metrics)
            report(
                "collecting",
                min(80, collect_start + int(((index + 1) / max(1, len(queries))) * collect_span)),
                aggregate_metrics,
            )
            if use_prefetched_index:
                interim_matches = _run_matcher(match_limit)
                if (
                    len(interim_matches) >= target_match_count
                    and _count_high_quality_matches(interim_matches) >= target_match_count
                ):
                    report("matching", 85, aggregate_metrics)
                    report("finalizing", 95, aggregate_metrics)
                    _commit_cursor()
                    return query, _absorb_matching_metrics(aggregate_metrics), interim_matches
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
                matches = _run_matcher(match_limit)
                report("finalizing", 95, aggregate_metrics)
                return query, _absorb_matching_metrics(aggregate_metrics), matches
        result = discover_and_index_vacancies(
            db,
            query=query,
            count=discover_count,
            rf_only=rf_only,
            force_reindex=False,
            use_brave_fallback=use_brave_fallback,
            max_analyzed=analyzed_budget,
            date_from=cursor_from,
        )
        fetch_succeeded = True
        aggregate_metrics = _merge_metrics(aggregate_metrics, result.metrics)
        report("collecting", 70, aggregate_metrics)

    report("matching", 85, aggregate_metrics)
    matches = _run_matcher(match_limit)
    report("finalizing", 95, aggregate_metrics)
    _commit_cursor()
    return query, _absorb_matching_metrics(aggregate_metrics), matches
