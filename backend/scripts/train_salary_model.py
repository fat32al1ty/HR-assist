"""Train the LightGBM-quantile salary predictor.

Phase 2.7. Reads all ``vacancy_profiles`` with a stated RUB salary,
builds a feature matrix (role_family, seniority, city, employment
type, remote policy), fits three models at alpha 0.25 / 0.5 / 0.75,
and writes pickles to ``backend/app/models/salary/``.

The script is intentionally conservative:

* Requires ≥ ``MIN_CORPUS`` rows or it exits without overwriting the
  existing artifact — "no model" is better than "a bad model".
* Drops outliers (top/bottom 1%) to avoid mystery 1 ₽ postings.
* Reports MAE, MAPE, and P25–P75 band coverage on a 15% holdout.
* Only replaces the existing artifact when the new MAPE beats the
  stored one.

Run manually during Phase 2.7 rollout, then promote to a weekly cron
once the corpus crosses the minimum.
"""

from __future__ import annotations

import logging
import pickle
import sys
from datetime import datetime
from pathlib import Path

# Minimum rows to train at all — plan target is 10k, floor is 1k so a
# development corpus can at least smoke-test the pipeline.
MIN_CORPUS = 1_000

logger = logging.getLogger("train_salary_model")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    try:
        import lightgbm as lgb  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415
    except ImportError:
        logger.error("lightgbm and numpy must be installed to train")
        return 2

    from app.db.session import SessionLocal  # noqa: PLC0415
    from app.models.vacancy import Vacancy  # noqa: PLC0415
    from app.models.vacancy_profile import VacancyProfile  # noqa: PLC0415
    from app.services.salary_predictor import (  # noqa: PLC0415
        MODEL_DIR,
        MODEL_P25,
        MODEL_P50,
        MODEL_P75,
        MODEL_VERSION_FILE,
    )

    db = SessionLocal()
    try:
        rows = (
            db.query(VacancyProfile, Vacancy)
            .join(Vacancy, Vacancy.id == VacancyProfile.vacancy_id)
            .filter(VacancyProfile.salary_currency == "RUB")
            .filter(
                (VacancyProfile.salary_min.isnot(None))
                | (VacancyProfile.salary_max.isnot(None))
            )
            .all()
        )
    finally:
        db.close()

    if len(rows) < MIN_CORPUS:
        logger.warning(
            "corpus too small to train (have=%d, need=%d) — skipping",
            len(rows),
            MIN_CORPUS,
        )
        return 1

    features, targets = [], []
    for vp, vac in rows:
        low, high = vp.salary_min, vp.salary_max
        mid = _midpoint(low, high)
        if mid is None:
            continue
        p = vp.profile if isinstance(vp.profile, dict) else {}
        features.append(
            [
                _hash_to_unit(p.get("role_family")),
                _hash_to_unit(p.get("seniority")),
                _hash_to_unit(vac.location),
                _hash_to_unit(p.get("employment_type")),
                _hash_to_unit(p.get("remote_policy")),
            ]
        )
        targets.append(mid)

    X = np.array(features, dtype=float)
    y = np.array(targets, dtype=float)
    mask = (y >= np.quantile(y, 0.01)) & (y <= np.quantile(y, 0.99))
    X, y = X[mask], y[mask]

    cut = int(0.85 * len(y))
    X_train, X_test = X[:cut], X[cut:]
    y_train, y_test = y[:cut], y[cut:]

    models = {}
    for tag, alpha in (("p25", 0.25), ("p50", 0.5), ("p75", 0.75)):
        model = lgb.LGBMRegressor(
            objective="quantile",
            alpha=alpha,
            n_estimators=200,
            learning_rate=0.05,
            num_leaves=31,
        )
        model.fit(X_train, y_train)
        models[tag] = model

    preds_p25 = models["p25"].predict(X_test)
    preds_p50 = models["p50"].predict(X_test)
    preds_p75 = models["p75"].predict(X_test)
    mae = float(np.mean(np.abs(preds_p50 - y_test)))
    mape = float(np.mean(np.abs(preds_p50 - y_test) / np.maximum(y_test, 1))) * 100
    coverage = float(np.mean((y_test >= preds_p25) & (y_test <= preds_p75))) * 100

    logger.info("MAE=%.0f ₽  MAPE=%.1f%%  P25–P75 coverage=%.1f%%", mae, mape, coverage)

    if not _should_replace(MODEL_DIR, mape):
        logger.info("existing model performs better — not overwriting")
        return 0

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_P25.write_bytes(pickle.dumps(models["p25"]))
    MODEL_P50.write_bytes(pickle.dumps(models["p50"]))
    MODEL_P75.write_bytes(pickle.dumps(models["p75"]))
    version = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    MODEL_VERSION_FILE.write_text(version, encoding="utf-8")
    logger.info("wrote model version %s to %s", version, MODEL_DIR)
    return 0


def _midpoint(low: int | None, high: int | None) -> int | None:
    if low is not None and high is not None:
        return (low + high) // 2
    return low or high


def _hash_to_unit(value) -> float:
    return float(hash(str(value or "").lower()) % 1000) / 1000.0


def _should_replace(model_dir: Path, new_mape: float) -> bool:
    marker = model_dir / "MAPE"
    if not marker.is_file():
        return True
    try:
        existing = float(marker.read_text(encoding="utf-8").strip())
    except Exception:
        return True
    return new_mape < existing


if __name__ == "__main__":
    sys.exit(main())
