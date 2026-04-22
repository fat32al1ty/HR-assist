"""Phase 1.9 PR B2 — taxonomy-backed skill expansion.

Bag-of-words and embedding matching both fail on bilingual concept
aliases: "планирование" in the vacancy vs "project management" on the
resume never meet in token space, and embedding fallback is both slow
and unreliable for short ambiguous phrases.

The taxonomy is a curated YAML file of ~50-80 clusters. Each cluster
lists RU + EN forms that should be treated as interchangeable for
matching purposes. Matching uses the taxonomy as an alias table — if
the vacancy phrase sits in a cluster and the resume has any other form
from the same cluster, we call it matched.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

_TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "data" / "skill_taxonomy.yaml"

# Matches the normalization in matching_service._normalize_phrase so the
# taxonomy lookup key aligns with how requirement strings are keyed
# before hitting `expand_concept`.
_NORMALIZE_SPLIT_RE = re.compile(r"[^0-9a-zA-Zа-яА-ЯёЁ+#]+")


def _normalize(value: str) -> str:
    normalized = _NORMALIZE_SPLIT_RE.sub(" ", (value or "").strip().lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _load_raw_clusters() -> list[dict]:
    try:
        with _TAXONOMY_PATH.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or []
    except FileNotFoundError:
        return []
    if not isinstance(data, list):
        return []
    clusters: list[dict] = []
    for entry in data:
        if isinstance(entry, dict):
            clusters.append(entry)
    return clusters


@lru_cache(maxsize=1)
def _build_phrase_to_forms() -> dict[str, frozenset[str]]:
    """Flatten taxonomy into {normalized_phrase: frozenset(all forms in same cluster)}.

    Both RU and EN forms end up as keys pointing at the *union* of RU + EN
    so lookup is locale-agnostic.
    """
    mapping: dict[str, frozenset[str]] = {}
    for cluster in _load_raw_clusters():
        ru = [_normalize(f) for f in cluster.get("forms_ru") or [] if isinstance(f, str)]
        en = [_normalize(f) for f in cluster.get("forms_en") or [] if isinstance(f, str)]
        all_forms = frozenset(f for f in (ru + en) if f)
        if not all_forms:
            continue
        for form in all_forms:
            mapping[form] = all_forms
    return mapping


def expand_concept(phrase: str) -> set[str]:
    """Return interchangeable forms for ``phrase`` (always includes phrase itself).

    Unknown phrases return a single-element set with just the lowercased
    phrase — callers can treat taxonomy as a no-op for misses and keep
    their existing matching logic.
    """
    if not isinstance(phrase, str):
        return set()
    key = _normalize(phrase)
    if not key:
        return set()
    mapping = _build_phrase_to_forms()
    forms = mapping.get(key)
    if forms is None:
        return {key}
    return set(forms)


def taxonomy_cluster_count() -> int:
    """Number of clusters currently loaded — used for startup logging / tests."""
    return len(_load_raw_clusters())


def reload_taxonomy() -> None:
    """Test-only hook: clear caches so a fresh YAML read happens next call."""
    _build_phrase_to_forms.cache_clear()
