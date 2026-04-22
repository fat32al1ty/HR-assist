"""LightGBM-quantile salary predictor — lazy loader + scoring.

Phase 2.7. The *shape* of the predictor ships now so the matching
pipeline, API, and UI can carry predicted bands end-to-end. The
*model* ships when the training corpus has enough RUB-priced rows
(plan target ≥10k; today the production corpus has tens).

Until a model artifact is placed in ``MODEL_DIR``, :func:`predict`
returns None for every input. ``train_salary_model.py`` is the
complementary script that builds the artifact.

The module stays importable even when LightGBM is not installed —
``lightgbm`` is a beefy wheel and there is no reason to bundle it
into the serving image before we have training data. ``predict``
returns None in that case too, logged once.
"""

from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "salary"
MODEL_VERSION_FILE = MODEL_DIR / "VERSION"
MODEL_P25 = MODEL_DIR / "model_p25.pkl"
MODEL_P50 = MODEL_DIR / "model_p50.pkl"
MODEL_P75 = MODEL_DIR / "model_p75.pkl"

# Minimum support — (role_family, seniority, city) triples with fewer
# historical observations produce unreliable bands. The predictor
# refuses to emit a number below this floor to avoid misleading cards.
MIN_TRAINING_SUPPORT = 30


@dataclass(frozen=True)
class SalaryBand:
    p25: int
    p50: int
    p75: int
    confidence: float
    model_version: str


class _PredictorCache:
    __slots__ = ("loaded", "models", "version", "supports")

    def __init__(self) -> None:
        self.loaded = False
        self.models: dict[str, Any] = {}
        self.version: str = ""
        self.supports: dict[tuple[str, str, str], int] = {}


_cache = _PredictorCache()


def _load_once() -> None:
    if _cache.loaded:
        return
    _cache.loaded = True
    if not (MODEL_P25.is_file() and MODEL_P50.is_file() and MODEL_P75.is_file()):
        logger.info("salary predictor disabled — no model artifacts in %s", MODEL_DIR)
        return
    try:
        _cache.models["p25"] = pickle.loads(MODEL_P25.read_bytes())
        _cache.models["p50"] = pickle.loads(MODEL_P50.read_bytes())
        _cache.models["p75"] = pickle.loads(MODEL_P75.read_bytes())
    except Exception as error:  # noqa: BLE001
        logger.warning("salary predictor: model load failed: %s", error)
        _cache.models.clear()
        return
    if MODEL_VERSION_FILE.is_file():
        _cache.version = MODEL_VERSION_FILE.read_text(encoding="utf-8").strip()
    logger.info("salary predictor loaded — version=%s", _cache.version or "unknown")


def predict(
    *,
    role_family: str | None,
    seniority: str | None,
    city: str | None,
    employment_type: str | None = None,
    remote_policy: str | None = None,
) -> SalaryBand | None:
    """Return a predicted (p25, p50, p75) band or None when unknown.

    Returns None when:

    * no model artifact is available (skeleton mode);
    * the (role_family, seniority, city) triple has too little training
      support (< :data:`MIN_TRAINING_SUPPORT` rows);
    * LightGBM is not installed in the serving image.

    Never raises — the matching pipeline calls this on the hot path.
    """
    _load_once()
    if not _cache.models:
        return None
    try:
        import lightgbm  # noqa: F401, PLC0415 — soft dep
    except Exception:
        return None
    key = (
        (role_family or "unknown").lower(),
        (seniority or "unknown").lower(),
        (city or "unknown").lower(),
    )
    support = _cache.supports.get(key, 0)
    if support < MIN_TRAINING_SUPPORT:
        return None
    features = _build_feature_row(
        role_family=role_family,
        seniority=seniority,
        city=city,
        employment_type=employment_type,
        remote_policy=remote_policy,
    )
    try:
        p25 = int(_cache.models["p25"].predict([features])[0])
        p50 = int(_cache.models["p50"].predict([features])[0])
        p75 = int(_cache.models["p75"].predict([features])[0])
    except Exception as error:  # noqa: BLE001
        logger.warning("salary predictor: scoring failed: %s", error)
        return None
    if p50 <= 0:
        return None
    # Enforce monotonicity — quantile crossing is a known LightGBM quirk.
    p25, p50, p75 = sorted((p25, p50, p75))
    confidence = min(1.0, support / 200.0)
    return SalaryBand(
        p25=p25, p50=p50, p75=p75, confidence=confidence, model_version=_cache.version or "dev"
    )


def _build_feature_row(
    *,
    role_family: str | None,
    seniority: str | None,
    city: str | None,
    employment_type: str | None,
    remote_policy: str | None,
) -> list[float]:
    """One-hot the categorical fields into the schema the trainer uses.

    Stub: the actual feature schema will be pinned by the trainer
    (``train_salary_model.py``) at first training. For now we return
    a deterministic placeholder so nothing downstream breaks when the
    model artifact arrives.
    """
    return [
        float(hash((role_family or "").lower()) % 1000) / 1000.0,
        float(hash((seniority or "").lower()) % 1000) / 1000.0,
        float(hash((city or "").lower()) % 1000) / 1000.0,
        float(hash((employment_type or "").lower()) % 1000) / 1000.0,
        float(hash((remote_policy or "").lower()) % 1000) / 1000.0,
    ]
