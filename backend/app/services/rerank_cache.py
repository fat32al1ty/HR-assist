"""Disk-backed cache for LLM rerank results.

Key: SHA-256 of ``(resume_id, sorted vacancy_id tuple, model)``. Value:
the JSON payload the LLM returned. Expires after
``llm_rerank_cache_ttl_hours``. Single-instance — no cross-worker
invalidation because each worker writes to the same directory and stale
entries are caught by mtime.

Design intent: keep the backend stateless; a cold start clears the
cache naturally because the directory lives under ``/app/storage``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


def _cache_dir() -> Path:
    directory = Path(settings.storage_dir) / "rerank_cache"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _key(resume_id: int, vacancy_ids: list[int], model: str) -> str:
    raw = f"{resume_id}|{','.join(str(v) for v in sorted(vacancy_ids))}|{model}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _path_for(key: str) -> Path:
    return _cache_dir() / f"{key}.json"


def read(resume_id: int, vacancy_ids: list[int], model: str) -> dict[str, Any] | None:
    path = _path_for(_key(resume_id, vacancy_ids, model))
    if not path.exists():
        return None
    ttl = settings.llm_rerank_cache_ttl_hours * 3600
    if time.time() - path.stat().st_mtime > ttl:
        try:
            path.unlink()
        except OSError:
            pass
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        logger.warning("rerank cache read failed for %s: %s", path.name, error)
        return None


def write(resume_id: int, vacancy_ids: list[int], model: str, payload: dict[str, Any]) -> None:
    path = _path_for(_key(resume_id, vacancy_ids, model))
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError as error:
        logger.warning("rerank cache write failed for %s: %s", path.name, error)
