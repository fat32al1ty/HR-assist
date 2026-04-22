"""Role-family enum + distance helpers.

The analyzer emits ``role_family`` and ``role_is_technical`` on both
resumes and vacancies. Downstream matching uses these as a coarse gate:

- If the resume is technical but the vacancy is not, hard-drop.
- Otherwise, apply a soft penalty scaled by ``family_distance``.

The family list is deliberately short (16 values) — coarser than ESCO
occupations but finer than the single technical/non-technical boolean.
When both sides have an ``esco_occupation_uri`` the ISCO-based
``role_distance`` takes over; this table is the fallback when the
analyzer couldn't resolve a URI.
"""

from __future__ import annotations

from typing import Final

ROLE_FAMILIES: Final[frozenset[str]] = frozenset(
    {
        "software_engineering",
        "data_ml",
        "infrastructure_devops",
        "cybersecurity",
        "hardware_embedded",
        "product_management",
        "design",
        "analytics_bi",
        "research_science",
        "marketing_growth",
        "sales_bd",
        "customer_support",
        "finance_accounting",
        "legal_compliance",
        "hr_talent",
        "operations_admin",
    }
)

TECHNICAL_FAMILIES: Final[frozenset[str]] = frozenset(
    {
        "software_engineering",
        "data_ml",
        "infrastructure_devops",
        "cybersecurity",
        "hardware_embedded",
    }
)

# Coarse groupings for the distance table. Families inside the same
# group are "close" (0.25), across groups are "far" (0.75), with 0.5
# reserved for adjacent-group pairings we know bridge in practice.
_FAMILY_GROUP: Final[dict[str, str]] = {
    "software_engineering": "engineering",
    "data_ml": "engineering",
    "infrastructure_devops": "engineering",
    "cybersecurity": "engineering",
    "hardware_embedded": "engineering",
    "product_management": "product",
    "design": "product",
    "analytics_bi": "product",
    "research_science": "research",
    "marketing_growth": "go_to_market",
    "sales_bd": "go_to_market",
    "customer_support": "go_to_market",
    "finance_accounting": "back_office",
    "legal_compliance": "back_office",
    "hr_talent": "back_office",
    "operations_admin": "back_office",
}

# Pairs that bridge two groups — used to soften the distance when a
# family spans engineering + product responsibilities. Symmetric.
_BRIDGE_PAIRS: Final[frozenset[frozenset[str]]] = frozenset(
    {
        frozenset({"analytics_bi", "data_ml"}),
        frozenset({"product_management", "software_engineering"}),
        frozenset({"design", "software_engineering"}),
        frozenset({"research_science", "data_ml"}),
    }
)


def family_distance(a: str | None, b: str | None) -> float:
    """Return a ``[0, 1]`` distance between two role families.

    Missing on either side returns 0.0 (can't penalise what we don't
    know). Returns 0.0 for identical families, 0.25 for families in the
    same group, 0.5 for a known bridge pair, 0.75 otherwise.
    """
    if not a or not b:
        return 0.0
    if a == b:
        return 0.0
    if a not in ROLE_FAMILIES or b not in ROLE_FAMILIES:
        return 0.0
    if frozenset({a, b}) in _BRIDGE_PAIRS:
        return 0.5
    if _FAMILY_GROUP.get(a) == _FAMILY_GROUP.get(b):
        return 0.25
    return 0.75
