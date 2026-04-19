from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, dashboard, health, resumes, system, vacancies
from app.core.config import settings, validate_runtime_settings
from app.services.vacancy_warmup import start_vacancy_warmup_worker, stop_vacancy_warmup_worker
from app.services.vector_store import ensure_default_vector_collections


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_runtime_settings()
    ensure_default_vector_collections()
    start_vacancy_warmup_worker()
    yield
    stop_vacancy_warmup_worker()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(resumes.router, prefix="/api/resumes", tags=["resumes"])
app.include_router(vacancies.router, prefix="/api/vacancies", tags=["vacancies"])
