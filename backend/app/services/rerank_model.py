"""Cross-encoder reranker — singleton loader.

Defers the heavy ``sentence_transformers`` import until first use so
cold-start latency is only paid when rerank is actually enabled. The
model is cached on the module object; in multi-worker deploys each
worker loads its own copy but that's acceptable for a single-box
backend running one gunicorn worker today.

Model choice: ``BAAI/bge-reranker-v2-m3`` — multilingual RU+EN, ~568 MB
Apache-2.0. Swappable via ``settings.rerank_model_name`` if we need to
A/B against a smaller model on a constrained box.
"""

from __future__ import annotations

import logging
from threading import Lock
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_MODEL: Any = None
_LOCK = Lock()


def get_reranker() -> Any:
    """Return the loaded CrossEncoder, instantiating on first call.

    Subsequent calls return the cached instance. Call sites must assume
    the load can take 5-15 s on the first invocation (HF Hub download +
    model-to-CPU materialisation).
    """
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _LOCK:
        if _MODEL is not None:
            return _MODEL
        from sentence_transformers import CrossEncoder  # noqa: PLC0415

        logger.info("loading cross-encoder %s", settings.rerank_model_name)
        _MODEL = CrossEncoder(settings.rerank_model_name, max_length=512)
        logger.info("cross-encoder %s loaded", settings.rerank_model_name)
        return _MODEL


def predict_pairs(pairs: list[tuple[str, str]]) -> list[float]:
    """Thin wrapper that returns plain floats (not numpy scalars).

    Empty input returns an empty list without touching the model.
    """
    if not pairs:
        return []
    model = get_reranker()
    scores = model.predict(pairs, batch_size=settings.rerank_batch_size)
    return [float(s) for s in scores]
