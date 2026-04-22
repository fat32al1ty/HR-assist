from datetime import datetime

from fastapi import APIRouter

from app.services.vacancy_warmup import get_vacancy_warmup_status

router = APIRouter()


@router.get("/vacancy-warmup")
def vacancy_warmup_status() -> dict[str, object]:
    full = get_vacancy_warmup_status()
    last_finished = full.get("last_finished_at")
    return {
        "enabled": bool(full.get("enabled")),
        "running": bool(full.get("running")),
        "last_finished_at": last_finished if isinstance(last_finished, datetime) else None,
        "interval_seconds": int(full.get("interval_seconds", 0)),
    }
