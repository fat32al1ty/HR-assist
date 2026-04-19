from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.vacancy_warmup import get_vacancy_warmup_status
from app.services.vector_store import get_vector_store

router = APIRouter()


@router.get("/config-check")
def config_check(db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        db.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception:
        database_status = "unavailable"

    jwt_secret_status = "configured"
    if settings.jwt_secret_key == "change-me-before-production":
        jwt_secret_status = "weak_default"

    vector_store_status = get_vector_store().healthcheck()

    return {
        "app_env": settings.app_env,
        "database": database_status,
        "openai": {
            "api_key": "configured" if settings.openai_api_key else "missing",
            "base_url": "configured" if settings.openai_base_url else "default",
            "analysis_model": settings.openai_analysis_model,
            "matching_model": settings.openai_matching_model,
            "reasoning_effort": settings.openai_reasoning_effort,
            "embedding_model": settings.openai_embedding_model,
        },
        "vector_store": {
            "provider": "qdrant",
            "status": vector_store_status["status"],
            "url": vector_store_status.get("url"),
            "collection_prefix": settings.qdrant_collection_prefix,
            "vector_size": settings.vector_size,
            "collections": vector_store_status.get("collections", []),
            "api_key": "configured" if settings.qdrant_api_key else "missing",
        },
        "vacancy_sources": {
            "brave_api": {
                "status": "configured" if settings.brave_api_key else "missing",
                "web_search_url": settings.brave_web_search_url,
            }
        },
        "jwt_secret_key": jwt_secret_status,
        "secrets": {
            "source": "runtime_environment",
            "values_exposed": False,
        },
    }


@router.get("/vacancy-warmup")
def vacancy_warmup_status() -> dict[str, object]:
    return get_vacancy_warmup_status()
