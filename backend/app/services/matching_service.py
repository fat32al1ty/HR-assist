import logging
import re
from math import sqrt
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.vacancy import Vacancy
from app.repositories.resume_user_skills import (
    list_added_skill_texts,
    list_rejected_skill_texts,
)
from app.repositories.resumes import get_resume_for_user
from app.repositories.user_vacancy_feedback import list_disliked_vacancy_ids, list_liked_vacancy_ids
from app.repositories.vacancies import get_vacancy_by_id
from app.services.embeddings import create_embedding
from app.services.resume_profile_pipeline import persist_resume_profile
from app.services.skill_taxonomy import expand_concept as expand_skill_concept
from app.services.user_preference_profile_pipeline import recompute_user_preference_profile
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)

TITLE_BOOST = 0.10
TITLE_BOOST_PARTIAL = 0.05
TITLE_BOOST_SCORE_CAP = 1.0

MIN_SKILLS_FOR_OVERLAP_FLOOR = 3
SENIORITY_PENALTY = 0.15
SENIORITY_MISMATCH_GAP = 2
TITLE_BOOST_TOKEN_STOPWORDS = {
    "and",
    "for",
    "the",
    "of",
    "to",
    "in",
    "with",
    "по",
    "на",
    "в",
    "и",
    "для",
    "над",
    "c",
    "с",
}
SENIORITY_RANK = {
    "intern": 0,
    "trainee": 0,
    "стажер": 0,
    "стажёр": 0,
    "junior": 1,
    "младший": 1,
    "middle": 2,
    "mid": 2,
    "средний": 2,
    "senior": 3,
    "старший": 3,
    "lead": 4,
    "techlead": 4,
    "tech lead": 4,
    "team lead": 4,
    "teamlead": 4,
    "тимлид": 4,
    "техлид": 4,
    "ведущий": 4,
    "staff": 5,
    "principal": 5,
    "head": 5,
    "director": 5,
    "руководитель": 5,
    "директор": 5,
    "c-level": 5,
}

ALLOWED_JOB_HOSTS = (
    "hh.ru",
    "career.habr.com",
    "superjob.ru",
)
BLOCKED_JOB_HOSTS = (
    "djinni.co",
    "workingnomads.com",
)
MIN_RELEVANCE_SCORE = 0.60
FALLBACK_MIN_RELEVANCE_SCORE = 0.50
RELAXED_MIN_RELEVANCE_SCORE = 0.40
STRONG_MATCH_THRESHOLD = MIN_RELEVANCE_SCORE
MAYBE_MATCH_THRESHOLD = 0.45
MAYBE_MATCH_CAP_DIVISOR = 2
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
# Substrings that indicate the domain is in the IT / software world.
# Used by the domain-compatibility gate — if either side has any of these markers,
# we treat the side as IT-rooted.
IT_DOMAIN_MARKERS = {
    "it ",
    "it-",
    " it",
    "айти",
    "айти-",
    "software",
    "saas",
    "paas",
    "iaas",
    "platform",
    "платформ",
    "devops",
    "sre",
    "site reliability",
    "observability",
    "monitoring",
    "мониторинг",
    "infrastructure",
    "инфраструктур",
    "information security",
    "информационн",
    "cybersecurity",
    "cloud",
    "облач",
    "kubernetes",
    "k8s",
    "backend",
    "frontend",
    "fullstack",
    "data engineering",
    "data platform",
    "data science",
    "дата-инжинир",
    "machine learning",
    "ml ",
    "mlops",
    "ai/ml",
    "ai platform",
    "llm",
    "blockchain",
    "fintech",
    "финтех",
    "quality assurance",
    "test automation",
    "database administration",
    "sysadmin",
    "системный администратор",
    "web development",
    "веб-разработ",
    "веб-разработка",
    "программирован",
    "разработка по",
    "разработка программ",
    "software development",
    "software engineering",
    "internet of things",
    "iot",
}
# Substrings that indicate a clearly non-IT industry.
# If a vacancy's domain contains any of these AND none of the IT markers above,
# AND the resume IS IT-rooted, we drop the vacancy as a domain mismatch.
NON_IT_DOMAIN_MARKERS = {
    "ремонт",
    "строитель",
    "строй",
    "сметн",
    "сметчик",
    "отделк",
    "монтажн",
    "автомобил",
    "автосервис",
    "автомехан",
    "автоэлектр",
    "дизайн интерьер",
    "интерьер",
    "медицин",
    "здравоохран",
    "фармац",
    "стоматол",
    "ветеринар",
    "юрист",
    "юридич",
    "адвокат",
    "нотариус",
    "общепит",
    "ресторан",
    "бариста",
    "повар",
    "кондитер",
    "пекарь",
    "кафе",
    "гостинич",
    "отель",
    "туризм",
    "туристич",
    "экскурс",
    "розничн",
    "продажа",
    "кассир",
    "продавец",
    "торговля",
    "склад",
    "грузчик",
    "логистик",
    "курьер",
    "водитель",
    "такси",
    "охран",
    "парикмах",
    "маникюр",
    "косметолог",
    "массаж",
    "фитнес",
    "тренер",
    "няня",
    "сиделка",
    "дошкольн",
    "школьн",
    "учитель",
    "воспитатель",
    "химическ",
    "биолог",
    "агро",
    "ферма",
    "животновод",
    "нефтегаз",
    "нефтян",
    "газов",
    "горнодобыв",
    "металлург",
    "машиностро",
    "станкостро",
    "серийное производство",
    "производств",
}


def _domain_corpus(domains: list[str] | None) -> str:
    if not isinstance(domains, list):
        return ""
    parts: list[str] = []
    for item in domains:
        if isinstance(item, str):
            text = item.strip().lower()
            if text:
                parts.append(text)
    return " ".join(parts)


def _has_domain_compatibility(
    resume_analysis: dict | None,
    vacancy_payload: dict | None,
) -> bool:
    """True unless we have strong evidence of an IT-vs-non-IT domain mismatch.

    Rules (in order):
    1. If either side declares no domains, pass (not enough signal).
    2. If any normalized token intersects (same industry or sub-industry), pass.
    3. If the vacancy side carries any IT marker, pass — cross-sub-domain IT moves are fine.
    4. If the resume is IT-rooted AND the vacancy carries a non-IT industry marker, DROP.
    5. Otherwise pass — ambiguous, let scoring decide.
    """
    resume_domains = resume_analysis.get("domains") if isinstance(resume_analysis, dict) else None
    vacancy_domains = vacancy_payload.get("domains") if isinstance(vacancy_payload, dict) else None
    res_text = _domain_corpus(resume_domains)
    vac_text = _domain_corpus(vacancy_domains)
    if not res_text or not vac_text:
        return True

    res_tokens = {token for token in _tokenize_text(res_text) if len(token) >= 3}
    vac_tokens = {token for token in _tokenize_text(vac_text) if len(token) >= 3}
    if res_tokens and vac_tokens:
        res_stems = {_stem_token(token) for token in res_tokens}
        vac_stems = {_stem_token(token) for token in vac_tokens}
        if res_stems.intersection(vac_stems):
            return True

    vacancy_is_it = any(marker in vac_text for marker in IT_DOMAIN_MARKERS)
    if vacancy_is_it:
        return True

    resume_is_it = any(marker in res_text for marker in IT_DOMAIN_MARKERS)
    vacancy_is_non_it = any(marker in vac_text for marker in NON_IT_DOMAIN_MARKERS)
    if resume_is_it and vacancy_is_non_it:
        return False
    return True


SKILL_ALIAS_GROUPS = (
    {"sre", "site reliability engineering", "site-reliability-engineering"},
    {
        "team lead",
        "tech lead",
        "тимлид",
        "техлид",
        "руководитель",
        "руководитель команды",
        "лид",
        "teamlead",
    },
    {
        "team leadership",
        "people management",
        "управление командой",
        "руководитель отдела",
        "head of",
        "line manager",
    },
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
    {
        "task management",
        "task prioritization",
        "backlog management",
        "постановка задач",
        "управление очередью задач",
    },
)
STRICT_REQUIREMENT_TOKENS = {"devops"}
LEADERSHIP_REQUIREMENT_TOKENS = {
    "teamlead",
    "team",
    "lead",
    "tech",
    "тимлид",
    "техлид",
    "руководитель",
    "manager",
    "head",
}
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
            if any(
                hint in sen
                for hint in (
                    "lead",
                    "head",
                    "manager",
                    "director",
                    "c-level",
                    "руковод",
                    "директор",
                )
            ):
                return True
    return False


def _extract_priority_anchors(analysis: dict | None) -> set[str]:
    if not isinstance(analysis, dict):
        return set()
    corpus = " ".join(
        [
            str(analysis.get("target_role") or ""),
            str(analysis.get("specialization") or ""),
            " ".join(
                [str(x) for x in (analysis.get("matching_keywords") or []) if isinstance(x, str)]
            ),
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
            domains_text = " ".join(
                str(item).strip().lower() for item in domains if isinstance(item, str)
            )
            if domains_text and any(marker in domains_text for marker in HARD_NON_IT_ROLE_MARKERS):
                return True

    text = f"{raw_text or ''}".lower()
    if text and "лаборатор" in text and "химичес" in text:
        return True
    return False


def _build_resume_skill_set(analysis: dict | None) -> set[str]:
    """Hard-skill token bag used for requirement-matching and overlap floor.

    Deliberately narrow — pulls from *curated* fields only:
    - hard_skills / skills / tools / matching_keywords (LLM-extracted skill phrases)
    - target_role / specialization (short structured role strings)
    - experience.role (short job title per position)

    Soft_skills, strengths, summary, and experience.highlights are free-form prose
    riddled with generic Russian connectors (опыт, знание, планирование, …) that
    bridged unrelated requirements via bag-of-words intersection and caused
    cross-domain false matches. Those fields still feed ``_build_resume_skill_phrases``,
    where the embedding-similarity path can use them without the bag-of-words trap.
    """
    if not isinstance(analysis, dict):
        return set()
    result: set[str] = set()
    for key in ("hard_skills", "skills", "tools", "matching_keywords"):
        result.update(_as_string_set(analysis.get(key)))
    for key in ("target_role", "specialization"):
        result.update(_tokenize_text(analysis.get(key)))
    experience = analysis.get("experience")
    if isinstance(experience, list):
        for item in experience:
            if isinstance(item, dict):
                result.update(_tokenize_text(item.get("role")))
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
    for key in (
        "hard_skills",
        "skills",
        "tools",
        "matching_keywords",
        "soft_skills",
        "strengths",
        "recommendations",
    ):
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
    for suffix in (
        "ing",
        "ment",
        "tion",
        "sion",
        "able",
        "ibility",
        "ость",
        "ение",
        "ция",
        "ии",
        "ый",
        "ий",
        "ая",
        "ые",
    ):
        if text.endswith(suffix) and len(text) - len(suffix) >= 3:
            return text[: -len(suffix)]
    return text


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
    resume_total_experience_years: float | None = None,
) -> bool:
    req = _normalize_phrase(requirement)
    if not req:
        return True

    # Phase 1.9 PR B1: answer "N+ years" quantitatively. If the requirement
    # is phrased as a year threshold and the candidate has at least that
    # many years on the resume, it's satisfied regardless of bag-of-words.
    required_years = _detect_quantitative_experience_requirement(requirement)
    if required_years is not None and resume_total_experience_years is not None:
        if resume_total_experience_years >= float(required_years):
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

    # Phase 1.9 PR B2: curated RU↔EN concept clusters. "планирование" in a
    # vacancy must match "project management" on a resume even though the
    # bag-of-words and phrase-alias layers miss the bilingual bridge.
    taxonomy_forms = expand_skill_concept(req)
    if taxonomy_forms:
        candidate_aliases: set[str] = set()
        for form in taxonomy_forms:
            candidate_aliases.update(_phrase_aliases(form))
        if candidate_aliases.intersection(resume_phrase_aliases):
            return True
        taxonomy_tokens: set[str] = set()
        for form in taxonomy_forms:
            taxonomy_tokens.update(_tokenize_rich_text(form))
        if taxonomy_tokens and taxonomy_tokens.intersection(resume_skill_tokens):
            return True

    for group in SKILL_ALIAS_GROUPS:
        normalized_group = {_normalize_phrase(item) for item in group}
        if req_tokens.intersection(normalized_group) and normalized_group.intersection(
            resume_phrase_aliases
        ):
            return True

    # Raw token intersection against the hard-skill token bag. Safe because
    # ``_build_resume_skill_set`` now excludes soft_skills/strengths — so generic
    # Russian words like "опыт"/"знание" can no longer bridge unrelated skills.
    if req_tokens.intersection(resume_skill_tokens):
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


# Phase 1.9 PR B1: quantitative experience detector.
# Pre-existing matching false-positives on "missing": senior candidates
# with 10+ years would see "опыт в IT от 3 лет" in the "не хватает"
# bucket because the phrase never appeared in their hard_skills bag.
# Detect the N-years ask quantitatively so we can answer it from
# resume.total_experience_years instead of bag-of-words.
_QUANT_EXPERIENCE_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\bот\s+(\d+)\s*(?:лет|года?|годов)\b", flags=re.IGNORECASE),
    re.compile(r"(\d+)\s*\+\s*(?:лет|года?|годов)\b", flags=re.IGNORECASE),
    re.compile(r"\bминимум\s+(\d+)\s*(?:лет|года?|годов)\b", flags=re.IGNORECASE),
    re.compile(r"\bне\s+менее\s+(\d+)\s*(?:лет|года?|годов)\b", flags=re.IGNORECASE),
    re.compile(r"(\d+)\s*(?:years?|yrs?)\b", flags=re.IGNORECASE),
    re.compile(r"(\d+)\s*\+\s*years?\b", flags=re.IGNORECASE),
)


def _detect_quantitative_experience_requirement(text: str) -> int | None:
    """Return the N from phrases like 'от N лет' / 'N+ years', else None."""
    if not isinstance(text, str) or not text:
        return None
    for pattern in _QUANT_EXPERIENCE_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                years = int(match.group(1))
            except (TypeError, ValueError):
                continue
            if 0 < years <= 40:
                return years
    return None


def _resume_total_experience_years(analysis: dict | None) -> float | None:
    if not isinstance(analysis, dict):
        return None
    raw = analysis.get("total_experience_years")
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return value


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


def _classify_requirements(
    payload: dict,
    resume_skills: set[str],
    *,
    resume_skill_phrases: list[str],
    resume_phrase_aliases: set[str],
    resume_phrase_vectors: dict[str, list[float]],
    embedding_cache: dict[str, list[float]],
    embedding_budget: dict[str, int],
    max_missing: int = SEMANTIC_GAP_MAX_REQUIREMENTS_PER_VACANCY,
    max_matched: int = 10,
    resume_total_experience_years: float | None = None,
) -> tuple[list[str], list[str]]:
    """Split a vacancy's required requirements into (matched, missing).

    Preserves original casing from the vacancy payload. The matched list is
    what the resume already satisfies; missing is the inverse.
    """
    required = _extract_required_requirements(payload)
    if not required:
        return [], []
    matched: list[str] = []
    missing: list[str] = []
    for requirement in required:
        is_match = _requirement_matches_resume(
            requirement,
            resume_skill_tokens=resume_skills,
            resume_skill_phrases=resume_skill_phrases,
            resume_phrase_aliases=resume_phrase_aliases,
            resume_phrase_vectors=resume_phrase_vectors,
            embedding_cache=embedding_cache,
            embedding_budget=embedding_budget,
            resume_total_experience_years=resume_total_experience_years,
        )
        if is_match:
            if len(matched) < max_matched:
                matched.append(requirement)
        else:
            if len(missing) < max_missing:
                missing.append(requirement)
    return matched, missing


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
    resume_total_experience_years: float | None = None,
) -> list[str]:
    _, missing = _classify_requirements(
        payload,
        resume_skills,
        resume_skill_phrases=resume_skill_phrases,
        resume_phrase_aliases=resume_phrase_aliases,
        resume_phrase_vectors=resume_phrase_vectors,
        embedding_cache=embedding_cache,
        embedding_budget=embedding_budget,
        max_missing=max_items,
        resume_total_experience_years=resume_total_experience_years,
    )
    return missing


def _matched_resume_skills_for_vacancy(
    resume_hard_skills: list[str],
    vacancy_skill_tokens: set[str],
    *,
    max_items: int = 10,
) -> list[str]:
    """Return which of the user's resume hard skills appear in this vacancy.

    Preserves original casing from the resume. Dedupes case-insensitively and
    uses alias groups so e.g. "k8s" in resume hits a vacancy asking for
    "kubernetes".
    """
    if not resume_hard_skills or not vacancy_skill_tokens:
        return []
    matched: list[str] = []
    seen_normalized: set[str] = set()
    for skill in resume_hard_skills:
        if not isinstance(skill, str):
            continue
        cleaned = skill.strip()
        if not cleaned:
            continue
        normalized = _normalize_phrase(cleaned)
        if not normalized or normalized in seen_normalized:
            continue

        skill_tokens = _tokenize_rich_text(cleaned)
        hit = False
        if skill_tokens and skill_tokens.intersection(vacancy_skill_tokens):
            hit = True
        if not hit:
            # Alias-group lookup so "k8s" on resume still counts when vacancy says "kubernetes".
            for alias in _phrase_aliases(cleaned):
                alias_tokens = _tokenize_rich_text(alias)
                if alias_tokens and alias_tokens.intersection(vacancy_skill_tokens):
                    hit = True
                    break
        if not hit:
            continue

        seen_normalized.add(normalized)
        matched.append(cleaned)
        if len(matched) >= max_items:
            break
    return matched


def _extract_resume_hard_skills(analysis: dict | None) -> list[str]:
    """Pick the user-facing hard-skills list (original casing, deduped)."""
    if not isinstance(analysis, dict):
        return []
    ordered: list[str] = []
    seen: set[str] = set()
    for key in ("hard_skills", "tools", "matching_keywords"):
        for item in _as_string_list(analysis.get(key)):
            normalized = _normalize_phrase(item)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(item.strip())
    return ordered


def _augment_profile_with_gap_insights(
    payload: dict | None,
    resume_skills: set[str],
    *,
    resume_hard_skills: list[str] | None = None,
    resume_skill_phrases: list[str],
    resume_phrase_aliases: set[str],
    resume_phrase_vectors: dict[str, list[float]],
    embedding_cache: dict[str, list[float]],
    embedding_budget: dict[str, int],
    resume_total_experience_years: float | None = None,
    vacancy_id: int | None = None,
    rejected_skill_norms: set[str] | None = None,
) -> dict:
    source_profile: dict = payload if isinstance(payload, dict) else {}
    profile = dict(source_profile)
    matched_requirements, missing = _classify_requirements(
        source_profile,
        resume_skills,
        resume_skill_phrases=resume_skill_phrases,
        resume_phrase_aliases=resume_phrase_aliases,
        resume_phrase_vectors=resume_phrase_vectors,
        embedding_cache=embedding_cache,
        embedding_budget=embedding_budget,
        resume_total_experience_years=resume_total_experience_years,
    )
    # Phase 1.9 PR C1: strip rejected skills from output so the UI
    # doesn't keep showing items the user explicitly disowned.
    rejected = rejected_skill_norms or set()
    if rejected:
        matched_requirements = [
            req for req in matched_requirements if _normalize_phrase(req) not in rejected
        ]
    # Phase 1.9 PR B1 telemetry: log the "не хватает" list so we can audit
    # false positives offline without surfacing per-vacancy logging in the UI.
    if missing:
        try:
            logger.info(
                "matching.missing_requirement vacancy_id=%s count=%d items=%s",
                vacancy_id,
                len(missing),
                missing,
            )
        except Exception:
            pass
    profile["missing_requirements"] = missing
    profile["missing_requirements_count"] = len(missing)
    profile["required_requirements_count"] = len(_extract_required_requirements(source_profile))
    profile["matched_requirements"] = matched_requirements
    vacancy_skill_tokens = _build_vacancy_skill_set(source_profile)
    matched_skills = _matched_resume_skills_for_vacancy(
        resume_hard_skills or [], vacancy_skill_tokens
    )
    if rejected:
        matched_skills = [s for s in matched_skills if _normalize_phrase(s) not in rejected]
    profile["matched_skills"] = matched_skills
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
    prefs: dict[str, object] | None = None,
    drop_counters: dict[str, int] | None = None,
) -> list[dict]:
    if not resume_skills:
        return []
    active_prefs = prefs or {}
    preferred_titles = active_prefs.get("preferred_titles") or []

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

        if active_prefs:
            lexical_drop = _hard_filter_drop_reason(
                vacancy_profile=None,
                vacancy_location=vacancy.location,
                prefs=active_prefs,
            )
            if lexical_drop == "geo":
                if drop_counters is not None:
                    drop_counters["geo"] = drop_counters.get("geo", 0) + 1
                continue
            # Work-format filter skipped here: lexical fallback has no
            # parsed remote_policy to compare against. Main-path filter
            # already culled format mismatches.

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
        title_boost = _preferred_title_boost_score(vacancy.title, preferred_titles)
        if title_boost > 0.0:
            score = min(TITLE_BOOST_SCORE_CAP, score + title_boost)
            if title_boost >= TITLE_BOOST and drop_counters is not None:
                drop_counters["title_boost"] = drop_counters.get("title_boost", 0) + 1
        if score < RELAXED_MIN_RELEVANCE_SCORE:
            continue
        dedupe_key = (
            f"{(vacancy.title or '').strip().lower()}::{(vacancy.company or '').strip().lower()}"
        )
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
                        "matched_requirements": [],
                        "matched_skills": [],
                    },
                },
            )
        )

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in ranked[:limit]]


def _normalize_remote_policy(value: object) -> str:
    """Map a free-form LLM remote_policy string to {remote, hybrid, office, unclear}.

    Unrecognized / missing values return "unclear" — we prefer to keep vacancies
    visible rather than hard-drop them when the LLM was ambiguous.
    """
    if not isinstance(value, str):
        return "unclear"
    text = value.strip().lower()
    if not text:
        return "unclear"
    remote_markers = ("remote", "удален", "удалён", "дистанц", "distributed", "anywhere")
    hybrid_markers = ("hybrid", "гибрид", "частично", "mixed")
    office_markers = ("office", "офис", "onsite", "on-site", "on site", "очно", "in-office")
    # Hybrid markers checked first because "частично удалённо" (partial remote)
    # literally contains "удалён" and would otherwise be misclassified as remote.
    if any(marker in text for marker in hybrid_markers):
        return "hybrid"
    if any(marker in text for marker in remote_markers):
        return "remote"
    if any(marker in text for marker in office_markers):
        return "office"
    return "unclear"


def _normalize_city_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = value.lower().strip()
    text = re.sub(r"^(г\.|город|city of|city)\s+", "", text)
    text = re.sub(r"[^0-9a-zа-яё\s-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _location_matches_home(location: object, home_city: str) -> bool:
    home_norm = _normalize_city_text(home_city)
    if not home_norm:
        return False
    loc_norm = _normalize_city_text(location)
    if not loc_norm:
        return False
    return home_norm in loc_norm


def _resolve_user_preferences(
    user: User | None,
    overrides: dict | None,
) -> dict[str, object]:
    """Merge persistent user prefs with optional per-request overrides.

    Overrides do not persist — they let a user say "just this one search, any city".
    Empty/None override values fall through to the user's stored preference.
    """
    base = {
        "preferred_work_format": getattr(user, "preferred_work_format", "any") or "any",
        "relocation_mode": getattr(user, "relocation_mode", "home_only") or "home_only",
        "home_city": getattr(user, "home_city", None),
        "preferred_titles": list(getattr(user, "preferred_titles", None) or []),
    }
    if not isinstance(overrides, dict):
        return base
    for key in ("preferred_work_format", "relocation_mode"):
        value = overrides.get(key)
        if isinstance(value, str) and value.strip():
            base[key] = value.strip()
    if "home_city" in overrides:
        value = overrides["home_city"]
        base["home_city"] = value.strip() if isinstance(value, str) and value.strip() else None
    titles = overrides.get("preferred_titles")
    if isinstance(titles, list):
        cleaned = [item.strip() for item in titles if isinstance(item, str) and item.strip()]
        base["preferred_titles"] = cleaned
    return base


def _hard_filter_drop_reason(
    *,
    vacancy_profile: dict | None,
    vacancy_location: str | None,
    prefs: dict[str, object],
) -> str | None:
    """Return the reason this vacancy should be dropped, or None to keep.

    Reasons: 'work_format', 'geo'. Keep semantics:
    - Work format: drop only when user picked a *definite* preference
      (remote/hybrid/office) AND the vacancy's normalized remote_policy is a
      *different* definite value. 'unclear' passes (conservative).
    - Geo: drop when relocation_mode=home_only AND home_city set AND vacancy
      location does not contain the home city AND vacancy isn't remote.
    """
    profile = vacancy_profile if isinstance(vacancy_profile, dict) else {}
    remote_policy = _normalize_remote_policy(profile.get("remote_policy"))

    pref_format = str(prefs.get("preferred_work_format") or "any").lower()
    if (
        pref_format in {"remote", "hybrid", "office"}
        and remote_policy
        in {
            "remote",
            "hybrid",
            "office",
        }
        and remote_policy != pref_format
    ):
        return "work_format"

    relocation = str(prefs.get("relocation_mode") or "home_only").lower()
    home_city = prefs.get("home_city") if isinstance(prefs.get("home_city"), str) else None
    if (
        relocation == "home_only"
        and home_city
        and remote_policy != "remote"
        and not _location_matches_home(vacancy_location, home_city)
    ):
        # Fall back to profile location if the vacancy row has no location set.
        profile_location = profile.get("location") if isinstance(profile, dict) else None
        if not _location_matches_home(profile_location, home_city):
            return "geo"

    return None


def _preferred_title_match(vacancy_title: object, preferred_titles: list[str]) -> bool:
    if not preferred_titles or not isinstance(vacancy_title, str):
        return False
    normalized_title = _normalize_phrase(vacancy_title)
    if not normalized_title:
        return False
    # Also compare a space-compressed form so "senior backend" matches
    # "senior back-end" (normalizer turns "back-end" into "back end").
    compact_title = normalized_title.replace(" ", "")
    for raw in preferred_titles:
        needle = _normalize_phrase(raw)
        if not needle:
            continue
        if needle in normalized_title:
            return True
        compact_needle = needle.replace(" ", "")
        if compact_needle and compact_needle in compact_title:
            return True
    return False


def _preferred_title_boost_score(vacancy_title: object, preferred_titles: list[str]) -> float:
    """Tiered title boost: full +0.10 on substring hit, +0.05 on token overlap.

    Falls back to non-stopword token overlap when a literal substring match
    fails. 2+ shared tokens → full boost; exactly 1 → partial boost.
    """
    if _preferred_title_match(vacancy_title, preferred_titles):
        return TITLE_BOOST
    if not preferred_titles or not isinstance(vacancy_title, str):
        return 0.0
    title_tokens = {
        token
        for token in _tokenize_rich_text(vacancy_title)
        if token not in TITLE_BOOST_TOKEN_STOPWORDS
    }
    if not title_tokens:
        return 0.0
    best = 0
    for raw in preferred_titles:
        if not isinstance(raw, str):
            continue
        needle_tokens = {
            token for token in _tokenize_rich_text(raw) if token not in TITLE_BOOST_TOKEN_STOPWORDS
        }
        if not needle_tokens:
            continue
        overlap_count = len(title_tokens.intersection(needle_tokens))
        if overlap_count > best:
            best = overlap_count
    if best >= 2:
        return TITLE_BOOST
    if best == 1:
        return TITLE_BOOST_PARTIAL
    return 0.0


def _required_skill_tokens(payload: dict) -> set[str]:
    """Set of normalized tokens from a vacancy's declared must-have skills."""
    tokens: set[str] = set()
    for requirement in _extract_required_requirements(payload):
        tokens.update(_tokenize_rich_text(requirement))
    return tokens


def _has_sufficient_skill_overlap(
    resume_skills: set[str],
    resume_hard_skills: list[str],
    vacancy_payload: dict,
) -> bool:
    """True when the floor doesn't apply OR at least one skill bridges both sides.

    The floor only kicks in when both the resume and the vacancy declare at least
    `MIN_SKILLS_FOR_OVERLAP_FLOOR` explicit skills — otherwise we don't trust the
    signal enough to hard-drop. When it does apply, we require at least one token
    overlap (alias-aware via resume_skills which already expands aliases).
    """
    required_tokens = _required_skill_tokens(vacancy_payload)
    if len(resume_hard_skills) < MIN_SKILLS_FOR_OVERLAP_FLOOR:
        return True
    if len(required_tokens) < MIN_SKILLS_FOR_OVERLAP_FLOOR:
        return True
    if resume_skills.intersection(required_tokens):
        return True
    return False


def _seniority_from_value(value: object) -> int | None:
    """Return a seniority rank 0-5 or None if the input can't be classified."""
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if not text:
        return None
    if text in SENIORITY_RANK:
        return SENIORITY_RANK[text]
    for key, rank in SENIORITY_RANK.items():
        if key in text:
            return rank
    return None


def _seniority_mismatch_penalty(
    resume_analysis: dict | None,
    vacancy_payload: dict | None,
) -> float:
    """Return additive penalty (0.0 or -SENIORITY_PENALTY) for grade mismatch.

    Applied when both sides declare seniority and the gap is ≥ 2 ranks.
    Neighboring grades (senior/lead, middle/senior) pass through untouched.
    """
    if not isinstance(resume_analysis, dict) or not isinstance(vacancy_payload, dict):
        return 0.0
    resume_rank = _seniority_from_value(resume_analysis.get("seniority"))
    vacancy_rank = _seniority_from_value(vacancy_payload.get("seniority"))
    if resume_rank is None or vacancy_rank is None:
        return 0.0
    if abs(resume_rank - vacancy_rank) >= SENIORITY_MISMATCH_GAP:
        return -SENIORITY_PENALTY
    return 0.0


def match_vacancies_for_resume(
    db: Session,
    *,
    resume_id: int,
    user_id: int,
    limit: int = 20,
    preference_overrides: dict | None = None,
    metrics: dict | None = None,
) -> list[dict]:
    resume = get_resume_for_user(db, resume_id=resume_id, user_id=user_id)
    if resume is None:
        return []

    try:
        user = db.get(User, user_id)
    except (AttributeError, TypeError):
        user = None
    prefs = _resolve_user_preferences(user, preference_overrides)
    preferred_titles = prefs.get("preferred_titles") or []
    drop_work_format = 0
    drop_geo = 0
    drop_no_skill_overlap = 0
    drop_domain_mismatch = 0
    seniority_penalty_applied = 0
    archived_at_match_time = 0
    title_boosts = 0

    vector_store = get_vector_store()
    query_vector = vector_store.get_resume_vector(resume_id=resume_id)
    if query_vector is None:
        if isinstance(resume.analysis, dict) and resume.analysis:
            try:
                persist_resume_profile(
                    db, resume_id=resume_id, user_id=user_id, profile=resume.analysis
                )
                query_vector = vector_store.get_resume_vector(resume_id=resume_id)
            except Exception:
                query_vector = None
    if query_vector is None:
        return []

    recompute_user_preference_profile(db, user_id=user_id, resume_id=resume_id)
    positive_pref, negative_pref = vector_store.get_user_preference_vectors(
        user_id=user_id, resume_id=resume_id
    )
    query_vector = _blend_resume_with_preferences(query_vector, positive_pref, negative_pref)

    resume_skills = _build_resume_skill_set(resume.analysis)
    resume_roles = _build_resume_role_set(resume.analysis)
    resume_skill_phrases = _build_resume_skill_phrases(resume.analysis)
    resume_hard_skills = _extract_resume_hard_skills(resume.analysis)
    resume_total_years = _resume_total_experience_years(resume.analysis)

    # Phase 1.9 PR C1: user-curated skills override the LLM parse.
    # `added` skills get folded into every resume-side input the matcher
    # looks at (token bag, phrases, hard-skills list). `rejected` skills
    # are stripped from output (matched_requirements, matched_skills)
    # so the UI doesn't keep surfacing items the user explicitly
    # disowned — even if the matcher still thinks they align.
    user_added_skills = list_added_skill_texts(db, resume_id=resume_id)
    user_rejected_skills = list_rejected_skill_texts(db, resume_id=resume_id)
    if user_added_skills:
        existing_hard_lower = {s.lower() for s in resume_hard_skills}
        for skill in user_added_skills:
            resume_skill_phrases.append(skill)
            resume_skills.update(_tokenize_rich_text(skill))
            if skill.lower() not in existing_hard_lower:
                resume_hard_skills.append(skill)
                existing_hard_lower.add(skill.lower())
    rejected_normalized = {_normalize_phrase(s) for s in user_rejected_skills if s}
    rejected_normalized.discard("")

    resume_phrase_aliases: set[str] = set()
    for phrase in resume_skill_phrases:
        resume_phrase_aliases.update(_phrase_aliases(phrase))
    resume_phrase_vectors: dict[str, list[float]] = {}
    embedding_cache: dict[str, list[float]] = {}
    embedding_budget = {"calls_left": SEMANTIC_GAP_MAX_EMBED_CALLS}
    leadership_preferred = _resume_prefers_leadership(resume_roles)
    disliked_vacancy_ids = list_disliked_vacancy_ids(db, user_id=user_id, resume_id=resume_id)
    liked_vacancy_ids = list_liked_vacancy_ids(db, user_id=user_id, resume_id=resume_id)
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
            # Persist the detection so future runs skip the re-check.
            # We also evict the Qdrant point so retrieval K stops spending on
            # an archived row.
            try:
                vacancy.status = "filtered"
                vacancy.error_message = "archived detected at match time"
                db.add(vacancy)
                db.commit()
                vector_store.delete_vacancy_profile(vacancy_id=vacancy.id)
            except Exception:
                db.rollback()
            archived_at_match_time += 1
            continue
        if _looks_like_listing_page(vacancy.source_url, vacancy.title):
            continue
        if _looks_unlikely_stack(vacancy.title, resume_skills):
            continue
        if _looks_business_monitoring_role(vacancy.title or "", resume_skills):
            continue
        if _looks_hard_non_it_role(
            vacancy.title or "", payload if isinstance(payload, dict) else None, vacancy.raw_text
        ):
            continue

        if not _has_domain_compatibility(
            resume.analysis, payload if isinstance(payload, dict) else None
        ):
            drop_domain_mismatch += 1
            continue

        drop_reason = _hard_filter_drop_reason(
            vacancy_profile=payload if isinstance(payload, dict) else None,
            vacancy_location=vacancy.location,
            prefs=prefs,
        )
        if drop_reason == "work_format":
            drop_work_format += 1
            continue
        if drop_reason == "geo":
            drop_geo += 1
            continue

        payload_dict = payload if isinstance(payload, dict) else {}
        if not _has_sufficient_skill_overlap(resume_skills, resume_hard_skills, payload_dict):
            drop_no_skill_overlap += 1
            continue

        vacancy_skills = _build_vacancy_skill_set(payload)
        vacancy_title_tokens = _tokenize_rich_text(vacancy.title or "")
        overlap = _overlap_score(resume_skills, vacancy_skills)
        role_overlap = _overlap_score(resume_roles, vacancy_title_tokens) if resume_roles else 0.0
        hybrid = _hybrid_score(float(score), overlap) + (0.05 * role_overlap)
        has_leadership_hint = _title_has_leadership_hint(vacancy.title or "", payload_dict)
        if leadership_preferred:
            if has_leadership_hint:
                hybrid += LEADERSHIP_BONUS
            else:
                hybrid -= LEADERSHIP_MISSING_PENALTY

        seniority_delta = _seniority_mismatch_penalty(resume.analysis, payload_dict)
        if seniority_delta != 0.0:
            hybrid += seniority_delta
            seniority_penalty_applied += 1

        title_boost = _preferred_title_boost_score(vacancy.title, preferred_titles)
        if title_boost > 0.0:
            hybrid = min(TITLE_BOOST_SCORE_CAP, hybrid + title_boost)
            if title_boost >= TITLE_BOOST:
                title_boosts += 1

        dedupe_key = (
            f"{(vacancy.title or '').strip().lower()}::{(vacancy.company or '').strip().lower()}"
        )
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
                        resume_hard_skills=resume_hard_skills,
                        resume_skill_phrases=resume_skill_phrases,
                        resume_phrase_aliases=resume_phrase_aliases,
                        resume_phrase_vectors=resume_phrase_vectors,
                        embedding_cache=embedding_cache,
                        embedding_budget=embedding_budget,
                        resume_total_experience_years=resume_total_years,
                        vacancy_id=vacancy.id,
                        rejected_skill_norms=rejected_normalized,
                    ),
                },
            )
        )

    ranked_all.sort(key=lambda item: item[0], reverse=True)
    # Two-tier selection: strong picks first, then maybe fills below the strict
    # cutoff down to MAYBE_MATCH_THRESHOLD. Old behavior returned strict-only
    # and only fell back to 0.50+ when strict was empty — that discarded real
    # borderline signal users wanted to see. UI partitions on the `tier` key.
    ranked_strong = [item for item in ranked_all if item[0] >= STRONG_MATCH_THRESHOLD]
    ranked_maybe = [
        item for item in ranked_all if MAYBE_MATCH_THRESHOLD <= item[0] < STRONG_MATCH_THRESHOLD
    ]

    top_matches: list[dict] = []
    for _hybrid, payload in ranked_strong[:limit]:
        top_matches.append({**payload, "tier": "strong"})

    maybe_cap = limit if not ranked_strong else max(1, limit // MAYBE_MATCH_CAP_DIVISOR)
    for _hybrid, payload in ranked_maybe[:maybe_cap]:
        profile = payload.get("profile")
        if isinstance(profile, dict):
            profile = {**profile, "tier_reason": "below_strict_threshold"}
        else:
            profile = {"tier_reason": "below_strict_threshold"}
        top_matches.append({**payload, "tier": "maybe", "profile": profile})

    if not top_matches:
        # Last-resort mode: keep recommendations non-empty when candidates exist but strict
        # thresholds are too conservative for the current resume wording.
        ranked_relaxed = [item for item in ranked_all if item[0] >= RELAXED_MIN_RELEVANCE_SCORE]
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
                    "tier": "maybe",
                }
            )

    def _record_metrics(result: list[dict]) -> list[dict]:
        if metrics is not None:
            metrics["hard_filter_drop_work_format"] = drop_work_format
            metrics["hard_filter_drop_geo"] = drop_geo
            metrics["hard_filter_drop_no_skill_overlap"] = drop_no_skill_overlap
            metrics["hard_filter_drop_domain_mismatch"] = drop_domain_mismatch
            metrics["seniority_penalty_applied"] = seniority_penalty_applied
            metrics["archived_at_match_time"] = archived_at_match_time
            metrics["title_boost_applied"] = title_boosts
        return result

    if len(top_matches) >= limit:
        return _record_metrics(top_matches)
    if leadership_preferred and top_matches:
        return _record_metrics(top_matches[:limit])

    lexical_counters: dict[str, int] = {}
    lexical_candidates = _lexical_fallback_matches(
        db,
        resume_skills=resume_skills,
        resume_roles=resume_roles,
        excluded_vacancy_ids=excluded_set,
        limit=limit * 2,
        prefs=prefs,
        drop_counters=lexical_counters,
    )
    drop_geo += int(lexical_counters.get("geo", 0))
    title_boosts += int(lexical_counters.get("title_boost", 0))

    if not top_matches:
        if leadership_preferred:
            return _record_metrics([])
        return _record_metrics(lexical_candidates[:limit])

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
    return _record_metrics(merged[:limit])
