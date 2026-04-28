"""Canonical domain taxonomy for HR-Assist.

26 slugs mapped to hh.ru industry IDs. Free-form LLM domain strings are
normalized to slugs at write time so the matcher's set-intersection boost
fires on canonical equality instead of raw-string mismatch ("ИТ" ≠ "IT").

Adding a new alias: append to the aliases list of the matching slug. If a
brand-new domain appears that doesn't fit any slug, decide whether to add
a new slug (with hh_id) or drop it. Substring matching is intentionally
NOT used — short tokens like "IT" or "HR" would false-positive on
unrelated strings.
"""

from __future__ import annotations

DOMAIN_CANONICAL: dict[str, tuple[str, str, list[str]]] = {
    # slug : (hh_industry_id, display_name_ru, [aliases])
    # --- Technology ---
    "it": (
        "7",
        "Информационные технологии",
        [
            "IT",
            "ИТ",
            "it",
            "software",
            "интернет",
            "системная интеграция",
            "information technology",
            "tech",
            "технологии",
            "разработка",
            "Enterprise IT",
            "enterprise it",
            "AI products",
            "ai products",
            "искусственный интеллект",
            "ML",
            "ml",
            "data science",
            "информационные системы",
            "SaaS",
            "saas",
        ],
    ),
    "infosec": (
        "7",
        "Информационная безопасность",
        [
            "информационная безопасность",
            "ИБ",
            "кибербезопасность",
            "cybersecurity",
            "infosec",
            "SOC",
            "pentest",
            "SIEM",
            "безопасность данных",
        ],
    ),
    "telecom": (
        "9",
        "Телекоммуникации",
        [
            "телеком",
            "телекоммуникации",
            "telecom",
            "связь",
            "операторы связи",
            "5G",
            "инфраструктура связи",
        ],
    ),
    # --- Finance ---
    "finance": (
        "43",
        "Финансовый сектор",
        [
            "финансы",
            "финансовый сектор",
            "banking",
            "банки",
            "банк",
            "Banking",
            "страхование",
            "инвестиции",
            "управление активами",
            "asset management",
            "private equity",
            "венчурные инвестиции",
        ],
    ),
    "fintech": (
        "43",
        "Финтех",
        [
            "финтех",
            "fintech",
            "финансовые технологии",
            "banking tech",
            "необанк",
            "neobank",
            "payments",
            "платежи",
            "платёжные системы",
        ],
    ),
    # --- Trade & Retail ---
    "retail": (
        "41",
        "Розничная торговля",
        [
            "ритейл",
            "retail",
            "розничная торговля",
            "розница",
            "торговые сети",
            "FMCG",
            "fmcg",
            "торговля",
            "ТРЦ",
            "супермаркет",
            "e-commerce",
            "ecommerce",
            "онлайн-ритейл",
        ],
    ),
    "fmcg": (
        "42",
        "Товары народного потребления",
        [
            "FMCG",
            "fmcg",
            "товары народного потребления",
            "потребительские товары",
            "consumer goods",
            "FMCD",
            "непищевые товары",
        ],
    ),
    # --- Construction & Real Estate ---
    "construction": (
        "13",
        "Строительство и недвижимость",
        [
            "строительство",
            "недвижимость",
            "девелопмент",
            "real estate",
            "эксплуатация",
            "проектирование",
            "ГК",
            "ЖК",
            "стройка",
            "инжиниринг",
        ],
    ),
    # --- Logistics & Transport ---
    "logistics": (
        "5",
        "Логистика и транспорт",
        [
            "логистика",
            "транспорт",
            "перевозки",
            "склад",
            "ВЭД",
            "logistics",
            "supply chain",
            "цепочки поставок",
            "фулфилмент",
            "доставка",
            "экспедирование",
            "ТЛЦ",
        ],
    ),
    # --- Media, Marketing, PR, Design ---
    "media": (
        "11",
        "СМИ и медиа",
        [
            "медиа",
            "СМИ",
            "media",
            "издательство",
            "журналистика",
            "контент",
            "стриминг",
            "телевидение",
            "радио",
            "блогинг",
        ],
    ),
    "marketing": (
        "11",
        "Маркетинг, реклама, PR",
        [
            "маркетинг",
            "реклама",
            "PR",
            "BTL",
            "ATL",
            "SMM",
            "брендинг",
            "продюсирование",
            "digital marketing",
            "перформанс",
            "performance marketing",
            "дизайн агентство",
        ],
    ),
    # --- Industry & Manufacturing ---
    "manufacturing": (
        "33",
        "Производство и машиностроение",
        [
            "производство",
            "машиностроение",
            "промышленность",
            "тяжёлое машиностроение",
            "manufacturing",
            "завод",
            "промышленное оборудование",
            "станки",
            "комплектующие",
        ],
    ),
    "metallurgy": (
        "24",
        "Металлургия и металлообработка",
        [
            "металлургия",
            "металлообработка",
            "чёрная металлургия",
            "цветная металлургия",
            "сталь",
            "прокат",
        ],
    ),
    "chemicals": (
        "34",
        "Химическое производство",
        [
            "химическое производство",
            "химия",
            "удобрения",
            "нефтехимия",
            "petrochemicals",
            "фармхимия",
        ],
    ),
    # --- Energy & Resources ---
    "oil_gas": (
        "47",
        "Нефть и газ",
        [
            "нефтегаз",
            "нефть",
            "газ",
            "нефть и газ",
            "oil & gas",
            "oil and gas",
            "добыча углеводородов",
            "нефтедобыча",
            "газодобыча",
            "НГДУ",
        ],
    ),
    "energy": (
        "46",
        "Энергетика",
        [
            "энергетика",
            "электроэнергетика",
            "energy",
            "генерация",
            "сетевые компании",
            "ВИЭ",
            "возобновляемая энергетика",
            "атомная энергетика",
        ],
    ),
    "mining": (
        "45",
        "Добывающая отрасль",
        [
            "добывающая отрасль",
            "горнодобывающая",
            "шахты",
            "mining",
            "руда",
            "уголь",
            "добыча",
        ],
    ),
    # --- Healthcare & Pharma ---
    "healthcare": (
        "48",
        "Медицина и фармацевтика",
        [
            "медицина",
            "фармацевтика",
            "здравоохранение",
            "healthcare",
            "pharma",
            "клиника",
            "аптеки",
            "медтех",
            "MedTech",
            "биотех",
            "biotech",
        ],
    ),
    # --- Education ---
    "education": (
        "39",
        "Образование",
        [
            "образование",
            "образовательные учреждения",
            "edtech",
            "EdTech",
            "e-learning",
            "обучение",
            "университет",
            "школа",
            "корпоративное обучение",
        ],
    ),
    # --- HoReCa & Consumer Services ---
    "horeca": (
        "50",
        "Гостиницы, рестораны, общепит",
        [
            "HoReCa",
            "horeca",
            "общественное питание",
            "общепит",
            "рестораны",
            "гостиницы",
            "отели",
            "гостиничный бизнес",
            "кейтеринг",
            "фастфуд",
        ],
    ),
    "consumer_services": (
        "49",
        "Услуги для населения",
        [
            "услуги для населения",
            "бытовые услуги",
            "клининг",
            "красота",
            "фитнес",
            "wellness",
        ],
    ),
    # --- Professional Services ---
    "legal": (
        "44",
        "Юридические услуги",
        [
            "юриспруденция",
            "право",
            "юридические услуги",
            "legal",
            "адвокатура",
            "нотариат",
            "compliance",
            "комплаенс",
            "юридическое сопровождение",
        ],
    ),
    "business_services": (
        "44",
        "Услуги для бизнеса",
        [
            "услуги для бизнеса",
            "консалтинг",
            "consulting",
            "аутсорсинг",
            "outsourcing",
            "B2B",
            "b2b",
            "бизнес-услуги",
            "управленческий консалтинг",
        ],
    ),
    # --- Auto ---
    "automotive": (
        "15",
        "Автомобильный бизнес",
        [
            "авто",
            "automotive",
            "автомобильный бизнес",
            "автодилер",
            "дилерская сеть",
            "автосервис",
            "автопром",
        ],
    ),
    # --- Government & NGO ---
    "government": (
        "36",
        "Государственные организации",
        [
            "государственные организации",
            "госсектор",
            "госслужба",
            "government",
            "ГУП",
            "МУП",
            "федеральная служба",
        ],
    ),
    "ngo": (
        "37",
        "НКО и общественная деятельность",
        [
            "НКО",
            "некоммерческие организации",
            "благотворительность",
            "общественная деятельность",
            "NGO",
            "фонды",
            "партии",
        ],
    ),
}


# Build reverse lookup: lowercased alias → slug. Done at module load.
_ALIAS_TO_SLUG: dict[str, str] = {}
for _slug, (_hh_id, _display, _aliases) in DOMAIN_CANONICAL.items():
    # Slug itself + display name lowercased + every alias lowercased.
    _ALIAS_TO_SLUG[_slug.lower()] = _slug
    _ALIAS_TO_SLUG[_display.lower()] = _slug
    for _alias in _aliases:
        _ALIAS_TO_SLUG[_alias.lower().strip()] = _slug


def normalize_domain(raw: str | None) -> str | None:
    """Map a free-form domain string to a canonical slug, or None if unknown.

    Case-insensitive exact match against the alias dict. No substring or
    fuzzy logic — short tokens like "IT" would false-positive.
    """
    if not raw or not isinstance(raw, str):
        return None
    key = raw.strip().lower()
    if not key:
        return None
    return _ALIAS_TO_SLUG.get(key)


def normalize_domains(raw_list: list[str] | None) -> list[str]:
    """Normalize a list of free-form domains to canonical slugs.

    Drops unknowns, dedupes, preserves first-occurrence order.
    """
    if not raw_list:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in raw_list:
        slug = normalize_domain(item)
        if slug is None or slug in seen:
            continue
        seen.add(slug)
        result.append(slug)
    return result


def all_canonical_slugs() -> list[tuple[str, str]]:
    """Return [(slug, display_name)] for UI rendering (typeahead, picker)."""
    return [(slug, display) for slug, (_hh_id, display, _aliases) in DOMAIN_CANONICAL.items()]
