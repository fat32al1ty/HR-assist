import re
from math import sqrt
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models.vacancy import Vacancy
from app.repositories.resumes import get_resume_for_user
from app.repositories.user_vacancy_feedback import list_disliked_vacancy_ids, list_liked_vacancy_ids
from app.repositories.vacancies import get_vacancy_by_id
from app.services.embeddings import create_embedding
from app.services.resume_profile_pipeline import persist_resume_profile
from app.services.user_preference_profile_pipeline import recompute_user_preference_profile
from app.services.vector_store import get_vector_store

ALLOWED_JOB_HOSTS = (
    "hh.ru",
    "career.habr.com",
    "superjob.ru",
)
BLOCKED_JOB_HOSTS = (
    "djinni.co",
    "workingnomads.com",
)
MIN_RELEVANCE_SCORE = 0.55
FALLBACK_MIN_RELEVANCE_SCORE = 0.48
RELAXED_MIN_RELEVANCE_SCORE = 0.40
SEMANTIC_GAP_SIMILARITY_THRESHOLD = 0.84
SEMANTIC_GAP_MAX_REQUIREMENTS_PER_VACANCY = 8
SEMANTIC_GAP_MAX_RESUME_PHRASES = 36
SEMANTIC_GAP_MAX_EMBED_CALLS = 48
PRIMARY_VACANCY_SOURCE = "hh_api"
LEADERSHIP_BONUS = 0.03
LEADERSHIP_MISSING_PENALTY = 0.02
POSITIVE_PROFILE_WEIGHT = 0.25
NEGATIVE_PROFILE_WEIGHT = 0.18
UNLIKELY_STACK_TOKENS = {
    "1c",
    "ml",
    "mlops",
    "llm",
    "dwh",
    "dba",
    "fullstack",
    "qa",
    "dataops",
    "oracle",
    "android",
    "ios",
    "swift",
    "kotlin",
    "golang",
    "php",
    "salesforce",
}
LEADERSHIP_HINT_TOKENS = {
    "lead",
    "head",
    "manager",
    "director",
    "руководитель",
    "директор",
    "начальник",
    "тимлид",
    "teamlead",
    "team",
    "leadership",
}
PRIORITY_ANCHOR_TOKENS = {
    "observability",
    "monitoring",
    "мониторинг",
    "мониторинга",
    "монитор",
}
TECH_ANCHOR_TOKENS = {
    "devops",
    "sre",
    "observability",
    "monitoring",
    "мониторинг",
    "prometheus",
    "grafana",
    "zabbix",
    "victoriametrics",
    "opentelemetry",
    "kubernetes",
    "linux",
    "platform",
}
STRICT_TECH_ANCHOR_TOKENS = {
    "prometheus",
    "grafana",
    "zabbix",
    "victoriametrics",
    "opentelemetry",
    "kubernetes",
    "linux",
}
BUSINESS_ROLE_TOKENS = {
    "финансов",
    "под",
    "фт",
    "aml",
    "financial",
    "risk",
    "compliance",
    "продаж",
    "маркетинг",
    "smm",
    "магазин",
    "партнер",
}
HARD_NON_IT_ROLE_MARKERS = {
    "химик",
    "химическ",
    "лаборатор",
    "биолог",
    "биохим",
    "фармацев",
    "медицин",
    "ветеринар",
    "агроном",
    "микробиолог",
}
NON_IT_ALLOWLIST_MARKERS = {
    "devops",
    "sre",
    "software",
    "platform",
    "site reliability",
    "it ",
    "айти",
}
SKILL_ALIAS_GROUPS = (
    {"sre", "site reliability engineering", "site-reliability-engineering"},
    {"team lead", "tech lead", "тимлид", "техлид", "руководитель", "руководитель команды", "лид", "teamlead"},
    {"team leadership", "people management", "управление командой", "руководитель отдела", "head of", "line manager"},
    {"incident response", "incident management", "инцидент менеджмент", "инцидент-менеджмент"},
    {"k8s", "kubernetes", "kuber"},
    {"observability", "monitoring", "мониторинг"},
    {"platform engineering", "platform", "платформенная эксплуатация", "платформенные сервисы"},
    {
        "capacity planning",
        "workload planning",
        "resource planning",
        "strategic planning",
        "планирование загрузки",
        "планирование ресурсов",
        "планирование работ",
    },
    {"task management", "task prioritization", "backlog management", "постановка задач", "управление очередью задач"},
)
STRICT_REQUIREMENT_TOKENS = {"devops"}
LEADERSHIP_REQUIREMENT_TOKENS = {"teamlead", "team", "lead", "tech", "тимлид", "техлид", "руководитель", "manager", "head"}
CAPACITY_REQUIREMENT_TOKENS = {"capacity", "workload", "загрузк", "ресурс"}
CAPACITY_SIGNAL_TOKENS = {
    "planning",
    "plan",
    "стратег",
    "планир",
    "prioritization",
    "prioritized",
    "приоритет",
    "backlog",
    "delivery",
    "команд",
}


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
    has_uuid = bool(re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", path))
    if ("/jobs/" in path or "/vacancies/" in path or "/vakansii/" in path) and not has_digit and not has_uuid:
        return True

    return False


def _host_allowed_for_matching(source_url: str) -> bool:
    host = (urlparse(source_url).hostname or "").lower()
    if not host:
        return False
    if any(host == blocked or host.endswith(f".{blocked}") for blocked in BLOCKED_JOB_HOSTS):
        return False
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in ALLOWED_JOB_HOSTS)


def _as_string_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    result: set[str] = set()
    for item in value:
        if isinstance(item, str):
            text = item.strip().lower()
            if text:
                result.add(text)
    return result


def _tokenize_text(value: object) -> set[str]:
    if not isinstance(value, str):
        return set()
    normalized = re.sub(r"[^0-9a-zA-Zа-яА-ЯёЁ+#]+", " ", value.lower())
    tokens = [token.strip() for token in normalized.split()]
    return {token for token in tokens if len(token) >= 2}


def _tokenize_rich_text(value: str) -> set[str]:
    return _tokenize_text(value)


def _looks_unlikely_stack(title: str, resume_skills: set[str]) -> bool:
    title_tokens = _tokenize_rich_text(title)
    if not title_tokens:
        return False
    for token in title_tokens:
        if token in UNLIKELY_STACK_TOKENS and token not in resume_skills:
            return True
    return False


def _resume_prefers_leadership(resume_roles: set[str]) -> bool:
    if not resume_roles:
        return False
    for token in resume_roles:
        if token in LEADERSHIP_HINT_TOKENS:
            return True
    return False


def _title_has_leadership_hint(title: str, payload: dict | None = None) -> bool:
    tokens = _tokenize_rich_text(title)
    if any(token in LEADERSHIP_HINT_TOKENS for token in tokens):
        return True
    if isinstance(payload, dict):
        role = payload.get("role")
        if isinstance(role, str):
            role_tokens = _tokenize_rich_text(role)
            if any(token in LEADERSHIP_HINT_TOKENS for token in role_tokens):
                return True
        seniority = payload.get("seniority")
        if isinstance(seniority, str):
            sen = seniority.strip().lower()
            if any(hint in sen for hint in ("lead", "head", "manager", "director", "c-level", "руковод", "директор")):
                return True
    return False


def _extract_priority_anchors(analysis: dict | None) -> set[str]:
    if not isinstance(analysis, dict):
        return set()
    corpus = " ".join(
        [
            str(analysis.get("target_role") or ""),
            str(analysis.get("specialization") or ""),
            " ".join([str(x) for x in (analysis.get("matching_keywords") or []) if isinstance(x, str)]),
            " ".join([str(x) for x in (analysis.get("hard_skills") or []) if isinstance(x, str)]),
        ]
    ).lower()
    anchors: set[str] = set()
    for token in PRIORITY_ANCHOR_TOKENS:
        if token in corpus:
            anchors.add(token)
    return anchors


def _extract_technical_anchors(resume_skills: set[str], analysis: dict | None = None) -> set[str]:
    anchors = set()
    for skill in resume_skills:
        normalized = skill.strip().lower()
        if normalized in TECH_ANCHOR_TOKENS:
            anchors.add(normalized)
    if isinstance(analysis, dict):
        for key in ("target_role", "specialization"):
            value = analysis.get(key)
            if isinstance(value, str):
                tokens = _tokenize_rich_text(value)
                for token in tokens:
                    if token in TECH_ANCHOR_TOKENS:
                        anchors.add(token)
    return anchors


def _extract_strict_technical_anchors(resume_skills: set[str]) -> set[str]:
    anchors: set[str] = set()
    for skill in resume_skills:
        normalized = skill.strip().lower()
        if normalized in STRICT_TECH_ANCHOR_TOKENS:
            anchors.add(normalized)
    return anchors


def _looks_business_monitoring_role(title: str, resume_skills: set[str]) -> bool:
    strict_anchors = _extract_strict_technical_anchors(resume_skills)
    if not strict_anchors:
        return False
    normalized_title = str(title or "").strip().lower()
    if not normalized_title:
        return False
    return any(marker in normalized_title for marker in BUSINESS_ROLE_TOKENS)


def _looks_hard_non_it_role(title: str, payload: dict | None, raw_text: str | None) -> bool:
    title_text = str(title or "").strip().lower()
    if not title_text:
        return False
    if any(marker in title_text for marker in NON_IT_ALLOWLIST_MARKERS):
        return False
    if any(marker in title_text for marker in HARD_NON_IT_ROLE_MARKERS):
        return True

    if isinstance(payload, dict):
        domains = payload.get("domains")
        if isinstance(domains, list):
            domains_text = " ".join(str(item).strip().lower() for item in domains if isinstance(item, str))
            if domains_text and any(marker in domains_text for marker in HARD_NON_IT_ROLE_MARKERS):
                return True

    text = f"{raw_text or ''}".lower()
    if text and "лаборатор" in text and "химичес" in text:
        return True
    return False


def _build_resume_skill_set(analysis: dict | None) -> set[str]:
    if not isinstance(analysis, dict):
        return set()
    result: set[str] = set()
    for key in ("hard_skills", "skills", "tools", "matching_keywords", "soft_skills", "strengths"):
        result.update(_as_string_set(analysis.get(key)))
    for key in ("target_role", "specialization", "summary"):
        result.update(_tokenize_text(analysis.get(key)))
    experience = analysis.get("experience")
    if isinstance(experience, list):
        for item in experience:
            if not isinstance(item, dict):
                continue
            result.update(_tokenize_text(item.get("role")))
            highlights = item.get("highlights")
            if isinstance(highlights, list):
                for highlight in highlights:
                    result.update(_tokenize_text(highlight))
    return result


def _build_resume_role_set(analysis: dict | None) -> set[str]:
    if not isinstance(analysis, dict):
        return set()
    result: set[str] = set()
    result.update(_tokenize_text(analysis.get("target_role")))
    result.update(_tokenize_text(analysis.get("specialization")))
    return result


def _build_resume_skill_phrases(analysis: dict | None) -> list[str]:
    if not isinstance(analysis, dict):
        return []
    phrases: list[str] = []
    for key in ("hard_skills", "skills", "tools", "matching_keywords", "soft_skills", "strengths", "recommendations"):
        phrases.extend(_as_string_list(analysis.get(key)))
    for key in ("target_role", "specialization", "summary"):
        value = analysis.get(key)
        if isinstance(value, str) and value.strip():
            phrases.append(value.strip())
    experience = analysis.get("experience")
    if isinstance(experience, list):
        for item in experience:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            if isinstance(role, str) and role.strip():
                phrases.append(role.strip())
            highlights = item.get("highlights")
            if isinstance(highlights, list):
                for highlight in highlights:
                    if isinstance(highlight, str) and highlight.strip():
                        phrases.append(highlight.strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        normalized = _normalize_phrase(phrase)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(phrase.strip())
        if len(deduped) >= SEMANTIC_GAP_MAX_RESUME_PHRASES:
            break
    return deduped


def _build_vacancy_skill_set(payload: dict) -> set[str]:
    result: set[str] = set()
    for key in ("must_have_skills", "tools", "domains", "matching_keywords"):
        result.update(_as_string_set(payload.get(key)))
    result.update(_tokenize_text(payload.get("role")))
    result.update(_tokenize_text(payload.get("title")))
    result.update(_tokenize_text(payload.get("summary")))
    return result


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text:
                result.append(text)
    return result


def _normalize_phrase(value: str) -> str:
    normalized = re.sub(r"[^0-9a-zA-Zа-яА-ЯёЁ+#]+", " ", (value or "").strip().lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _phrase_aliases(value: str) -> set[str]:
    normalized = _normalize_phrase(value)
    if not normalized:
        return set()
    aliases = {normalized}
    for group in SKILL_ALIAS_GROUPS:
        normalized_group = {_normalize_phrase(item) for item in group}
        if normalized in normalized_group:
            aliases.update({item for item in normalized_group if item})
            continue
        if any(item and item in normalized for item in normalized_group):
            aliases.update({item for item in normalized_group if item})
    return aliases


def _stem_token(token: str) -> str:
    text = token.strip().lower()
    if len(text) <= 4:
        return text
    for suffix in ("ing", "ment", "tion", "sion", "able", "ibility", "ость", "ение", "ция", "ии", "ый", "ий", "ая", "ые"):
        if text.endswith(suffix) and len(text) - len(suffix) >= 3:
            return text[: -len(suffix)]
    return text


def _tokens_semantically_overlap(left: set[str], right: set[str]) -> bool:
    if not left or not right:
        return False
    if left.intersection(right):
        return True
    left_stems = {_stem_token(item) for item in left}
    right_stems = {_stem_token(item) for item in right}
    return bool(left_stems.intersection(right_stems))


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for l_value, r_value in zip(left, right):
        dot += float(l_value) * float(r_value)
        left_norm += float(l_value) * float(l_value)
        right_norm += float(r_value) * float(r_value)
    if left_norm <= 0.0 or right_norm <= 0.0:
        return 0.0
    return dot / (sqrt(left_norm) * sqrt(right_norm))


def _contains_token_fragment(tokens: set[str], fragments: set[str]) -> bool:
    for token in tokens:
        for fragment in fragments:
            if fragment and fragment in token:
                return True
    return False


def _embedding_for_phrase(
    phrase: str,
    *,
    embedding_cache: dict[str, list[float]],
    budget: dict[str, int],
) -> list[float] | None:
    normalized = _normalize_phrase(phrase)
    if not normalized:
        return None
    if normalized in embedding_cache:
        return embedding_cache[normalized]
    left_calls = int(budget.get("calls_left", 0))
    if left_calls <= 0:
        return None
    try:
        vector = create_embedding(normalized)
    except Exception:
        budget["calls_left"] = 0
        return None
    embedding_cache[normalized] = vector
    budget["calls_left"] = left_calls - 1
    return vector


def _requirement_matches_resume(
    requirement: str,
    *,
    resume_skill_tokens: set[str],
    resume_skill_phrases: list[str],
    resume_phrase_aliases: set[str],
    resume_phrase_vectors: dict[str, list[float]],
    embedding_cache: dict[str, list[float]],
    embedding_budget: dict[str, int],
) -> bool:
    req = _normalize_phrase(requirement)
    if not req:
        return True

    req_tokens = _tokenize_rich_text(req)
    if req_tokens.intersection(STRICT_REQUIREMENT_TOKENS):
        # For strict terms like "devops" require explicit presence in resume terms.
        return bool(req_tokens.intersection(resume_skill_tokens))
    if req_tokens.intersection(LEADERSHIP_REQUIREMENT_TOKENS):
        if resume_skill_tokens.intersection(LEADERSHIP_HINT_TOKENS):
            return True
    if _contains_token_fragment(req_tokens, CAPACITY_REQUIREMENT_TOKENS):
        if _contains_token_fragment(resume_skill_tokens, CAPACITY_SIGNAL_TOKENS):
            return True

    req_aliases = _phrase_aliases(req)
    if req_aliases.intersection(resume_phrase_aliases):
        return True

    for group in SKILL_ALIAS_GROUPS:
        normalized_group = {_normalize_phrase(item) for item in group}
        if req_tokens.intersection(normalized_group) and normalized_group.intersection(resume_phrase_aliases):
            return True
    if _tokens_semantically_overlap(req_tokens, resume_skill_tokens):
        return True

    req_vector = _embedding_for_phrase(
        req,
        embedding_cache=embedding_cache,
        budget=embedding_budget,
    )
    if req_vector is None:
        return False

    best = 0.0
    for phrase in resume_skill_phrases:
        phrase_norm = _normalize_phrase(phrase)
        if not phrase_norm:
            continue
        phrase_vector = resume_phrase_vectors.get(phrase_norm)
        if phrase_vector is None:
            phrase_vector = _embedding_for_phrase(
                phrase_norm,
                embedding_cache=embedding_cache,
                budget=embedding_budget,
            )
            if phrase_vector is not None:
                resume_phrase_vectors[phrase_norm] = phrase_vector
        if phrase_vector is None:
            continue
        similarity = _cosine_similarity(req_vector, phrase_vector)
        if similarity > best:
            best = similarity
        if best >= SEMANTIC_GAP_SIMILARITY_THRESHOLD:
            return True
    return False


def _extract_required_requirements(payload: dict) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for key in ("must_have_skills", "tools"):
        for item in _as_string_list(payload.get(key)):
            normalized = item.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(item.strip())
    return ordered


def _missing_requirements(
    payload: dict,
    resume_skills: set[str],
    *,
    resume_skill_phrases: list[str],
    resume_phrase_aliases: set[str],
    resume_phrase_vectors: dict[str, list[float]],
    embedding_cache: dict[str, list[float]],
    embedding_budget: dict[str, int],
    max_items: int = SEMANTIC_GAP_MAX_REQUIREMENTS_PER_VACANCY,
) -> list[str]:
    required = _extract_required_requirements(payload)
    if not required:
        return []
    missing: list[str] = []
    for requirement in required:
        if _requirement_matches_resume(
            requirement,
            resume_skill_tokens=resume_skills,
            resume_skill_phrases=resume_skill_phrases,
            resume_phrase_aliases=resume_phrase_aliases,
            resume_phrase_vectors=resume_phrase_vectors,
            embedding_cache=embedding_cache,
            embedding_budget=embedding_budget,
        ):
            continue
        missing.append(requirement)
        if len(missing) >= max_items:
            break
    return missing


def _augment_profile_with_gap_insights(
    payload: dict | None,
    resume_skills: set[str],
    *,
    resume_skill_phrases: list[str],
    resume_phrase_aliases: set[str],
    resume_phrase_vectors: dict[str, list[float]],
    embedding_cache: dict[str, list[float]],
    embedding_budget: dict[str, int],
) -> dict:
    source_profile: dict = payload if isinstance(payload, dict) else {}
    profile = dict(source_profile)
    missing = _missing_requirements(
        source_profile,
        resume_skills,
        resume_skill_phrases=resume_skill_phrases,
        resume_phrase_aliases=resume_phrase_aliases,
        resume_phrase_vectors=resume_phrase_vectors,
        embedding_cache=embedding_cache,
        embedding_budget=embedding_budget,
    )
    profile["missing_requirements"] = missing
    profile["missing_requirements_count"] = len(missing)
    profile["required_requirements_count"] = len(_extract_required_requirements(source_profile))
    return profile


def _overlap_score(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    inter = left.intersection(right)
    if not inter:
        return 0.0
    return len(inter) / float(max(len(left), len(right)))


def _hybrid_score(vector_score: float, overlap: float) -> float:
    # Keep semantic vector signal dominant; lexical overlap is a stabilizer.
    return (0.9 * vector_score) + (0.1 * overlap)


def _blend_resume_with_preferences(
    resume_vector: list[float],
    positive_vector: list[float] | None,
    negative_vector: list[float] | None,
) -> list[float]:
    if not resume_vector:
        return resume_vector
    length = len(resume_vector)
    if length == 0:
        return resume_vector

    has_positive = bool(positive_vector) and len(positive_vector or []) == length
    has_negative = bool(negative_vector) and len(negative_vector or []) == length
    if not has_positive and not has_negative:
        return resume_vector

    pos_weight = max(0.0, min(0.9, POSITIVE_PROFILE_WEIGHT))
    neg_weight = max(0.0, min(0.9, NEGATIVE_PROFILE_WEIGHT))
    blended: list[float] = []
    for index, base in enumerate(resume_vector):
        value = float(base)
        if has_positive and positive_vector is not None:
            value += pos_weight * float(positive_vector[index])
        if has_negative and negative_vector is not None:
            value -= neg_weight * float(negative_vector[index])
        blended.append(value)
    return blended


def _lexical_fallback_matches(
    db: Session,
    *,
    resume_skills: set[str],
    resume_roles: set[str],
    excluded_vacancy_ids: set[int],
    limit: int,
) -> list[dict]:
    if not resume_skills:
        return []

    candidates = (
        db.query(Vacancy)
        .filter(Vacancy.status == "indexed")
        .order_by(Vacancy.updated_at.desc())
        .limit(max(limit * 50, 400))
        .all()
    )
    ranked: list[tuple[float, dict]] = []
    seen_keys: set[str] = set()
    leadership_preferred = _resume_prefers_leadership(resume_roles)

    for vacancy in candidates:
        if vacancy.id in excluded_vacancy_ids:
            continue
        if (vacancy.source or "").strip().lower() != PRIMARY_VACANCY_SOURCE:
            continue
        if not _host_allowed_for_matching(vacancy.source_url):
            continue
        if _looks_non_vacancy_page(vacancy.source_url):
            continue
        if _looks_archived_vacancy_strict(vacancy.source_url, vacancy.title, vacancy.raw_text):
            continue
        if _looks_like_listing_page(vacancy.source_url, vacancy.title):
            continue
        if _looks_unlikely_stack(vacancy.title, resume_skills):
            continue
        if _looks_business_monitoring_role(vacancy.title or "", resume_skills):
            continue
        if _looks_hard_non_it_role(vacancy.title or "", None, vacancy.raw_text):
            continue

        text = " ".join(
            part
            for part in [
                vacancy.title or "",
                vacancy.company or "",
                vacancy.location or "",
                (vacancy.raw_text or "")[:4000],
            ]
            if part
        )
        vacancy_tokens = _tokenize_rich_text(text)
        overlap = _overlap_score(resume_skills, vacancy_tokens)
        title_tokens = _tokenize_rich_text(vacancy.title or "")
        role_overlap = _overlap_score(resume_roles, title_tokens) if resume_roles else 0.0
        if overlap <= 0.03:
            continue
        if resume_roles and role_overlap <= 0.0 and overlap < 0.10:
            continue

        score = min(0.95, 0.55 + overlap * 0.45)
        has_leadership_hint = _title_has_leadership_hint(vacancy.title or "")
        if leadership_preferred:
            if has_leadership_hint:
                score += LEADERSHIP_BONUS
            else:
                score -= LEADERSHIP_MISSING_PENALTY
        if score < RELAXED_MIN_RELEVANCE_SCORE:
            continue
        dedupe_key = f"{(vacancy.title or '').strip().lower()}::{(vacancy.company or '').strip().lower()}"
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        ranked.append(
            (
                score,
                {
                    "vacancy_id": vacancy.id,
                    "title": vacancy.title,
                    "source_url": vacancy.source_url,
                    "company": vacancy.company,
                    "location": vacancy.location,
                    "similarity_score": round(score, 5),
                    "profile": {
                        "source": "lexical_fallback",
                        "missing_requirements": [],
                        "missing_requirements_count": 0,
                        "required_requirements_count": 0,
                    },
                },
            )
        )

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in ranked[:limit]]


def match_vacancies_for_resume(
    db: Session,
    *,
    resume_id: int,
    user_id: int,
    limit: int = 20,
) -> list[dict]:
    resume = get_resume_for_user(db, resume_id=resume_id, user_id=user_id)
    if resume is None:
        return []

    vector_store = get_vector_store()
    query_vector = vector_store.get_resume_vector(resume_id=resume_id)
    if query_vector is None:
        if isinstance(resume.analysis, dict) and resume.analysis:
            try:
                persist_resume_profile(db, resume_id=resume_id, user_id=user_id, profile=resume.analysis)
                query_vector = vector_store.get_resume_vector(resume_id=resume_id)
            except Exception:
                query_vector = None
    if query_vector is None:
        return []

    recompute_user_preference_profile(db, user_id=user_id)
    positive_pref, negative_pref = vector_store.get_user_preference_vectors(user_id=user_id)
    query_vector = _blend_resume_with_preferences(query_vector, positive_pref, negative_pref)

    resume_skills = _build_resume_skill_set(resume.analysis)
    resume_roles = _build_resume_role_set(resume.analysis)
    resume_skill_phrases = _build_resume_skill_phrases(resume.analysis)
    resume_phrase_aliases: set[str] = set()
    for phrase in resume_skill_phrases:
        resume_phrase_aliases.update(_phrase_aliases(phrase))
    resume_phrase_vectors: dict[str, list[float]] = {}
    embedding_cache: dict[str, list[float]] = {}
    embedding_budget = {"calls_left": SEMANTIC_GAP_MAX_EMBED_CALLS}
    leadership_preferred = _resume_prefers_leadership(resume_roles)
    disliked_vacancy_ids = list_disliked_vacancy_ids(db, user_id=user_id)
    liked_vacancy_ids = list_liked_vacancy_ids(db, user_id=user_id)
    excluded_set = set(disliked_vacancy_ids).union(liked_vacancy_ids)
    search_limit = max(limit * 8, 120)
    found = vector_store.search_vacancy_profiles(query_vector=query_vector, limit=search_limit)

    ranked_all: list[tuple[float, dict]] = []
    seen_keys: set[str] = set()
    for vacancy_id, score, payload in found:
        if vacancy_id in excluded_set:
            continue
        if "is_vacancy" in payload and payload.get("is_vacancy") is not True:
            continue

        vacancy = get_vacancy_by_id(db, vacancy_id=vacancy_id)
        if vacancy is None or vacancy.status != "indexed":
            continue
        if (vacancy.source or "").strip().lower() != PRIMARY_VACANCY_SOURCE:
            continue
        if not _host_allowed_for_matching(vacancy.source_url):
            continue
        if _looks_non_vacancy_page(vacancy.source_url):
            continue
        if _looks_archived_vacancy_strict(vacancy.source_url, vacancy.title, vacancy.raw_text):
            continue
        if _looks_like_listing_page(vacancy.source_url, vacancy.title):
            continue
        if _looks_unlikely_stack(vacancy.title, resume_skills):
            continue
        if _looks_business_monitoring_role(vacancy.title or "", resume_skills):
            continue
        if _looks_hard_non_it_role(vacancy.title or "", payload if isinstance(payload, dict) else None, vacancy.raw_text):
            continue

        vacancy_skills = _build_vacancy_skill_set(payload)
        vacancy_title_tokens = _tokenize_rich_text(vacancy.title or "")
        overlap = _overlap_score(resume_skills, vacancy_skills)
        role_overlap = _overlap_score(resume_roles, vacancy_title_tokens) if resume_roles else 0.0
        hybrid = _hybrid_score(float(score), overlap) + (0.05 * role_overlap)
        has_leadership_hint = _title_has_leadership_hint(vacancy.title or "", payload if isinstance(payload, dict) else None)
        if leadership_preferred:
            if has_leadership_hint:
                hybrid += LEADERSHIP_BONUS
            else:
                hybrid -= LEADERSHIP_MISSING_PENALTY

        dedupe_key = f"{(vacancy.title or '').strip().lower()}::{(vacancy.company or '').strip().lower()}"
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        ranked_all.append(
            (
                hybrid,
                {
                    "vacancy_id": vacancy.id,
                    "title": vacancy.title,
                    "source_url": vacancy.source_url,
                    "company": vacancy.company,
                    "location": vacancy.location,
                    "similarity_score": round(hybrid, 5),
                    "profile": _augment_profile_with_gap_insights(
                        payload,
                        resume_skills,
                        resume_skill_phrases=resume_skill_phrases,
                        resume_phrase_aliases=resume_phrase_aliases,
                        resume_phrase_vectors=resume_phrase_vectors,
                        embedding_cache=embedding_cache,
                        embedding_budget=embedding_budget,
                    ),
                },
            )
        )

    ranked_all.sort(key=lambda item: item[0], reverse=True)
    ranked_strict = [item for item in ranked_all if item[0] >= MIN_RELEVANCE_SCORE]
    top_matches = [item[1] for item in ranked_strict[:limit]]
    if not top_matches:
        ranked_fallback = [item for item in ranked_all if item[0] >= FALLBACK_MIN_RELEVANCE_SCORE]
        top_matches = [item[1] for item in ranked_fallback[:limit]]
    if not top_matches:
        # Last-resort mode: keep recommendations non-empty when candidates exist but strict
        # thresholds are too conservative for the current resume wording.
        ranked_relaxed = [item for item in ranked_all if item[0] >= RELAXED_MIN_RELEVANCE_SCORE]
        top_matches = []
        for hybrid, payload in ranked_relaxed[:limit]:
            profile = payload.get("profile")
            if isinstance(profile, dict):
                profile = {**profile, "source": "relaxed_fallback", "fallback_tier": "relaxed"}
            else:
                profile = {"source": "relaxed_fallback", "fallback_tier": "relaxed"}
            top_matches.append(
                {
                    **payload,
                    "similarity_score": round(float(hybrid), 5),
                    "profile": profile,
                }
            )
    if len(top_matches) >= limit:
        return top_matches
    if leadership_preferred and top_matches:
        return top_matches[:limit]

    lexical_candidates = _lexical_fallback_matches(
        db,
        resume_skills=resume_skills,
        resume_roles=resume_roles,
        excluded_vacancy_ids=excluded_set,
        limit=limit * 2,
    )
    if not top_matches:
        if leadership_preferred:
            return []
        return lexical_candidates[:limit]

    present_ids = {int(item.get("vacancy_id", 0)) for item in top_matches}
    merged = list(top_matches)
    for item in lexical_candidates:
        vacancy_id = int(item.get("vacancy_id", 0))
        if vacancy_id <= 0 or vacancy_id in present_ids:
            continue
        merged.append(item)
        present_ids.add(vacancy_id)
        if len(merged) >= limit:
            break
    return merged[:limit]
