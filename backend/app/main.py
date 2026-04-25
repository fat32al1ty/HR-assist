from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.api.routes import (
    admin,
    applications,
    auth,
    dashboard,
    health,
    onboarding,
    resume_audit,
    resumes,
    system,
    telemetry,
    track_gaps,
    users,
    vacancies,
)
from app.core.config import settings, validate_runtime_settings
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
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
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(resumes.router, prefix="/api/resumes", tags=["resumes"])
app.include_router(resume_audit.router, prefix="/api/resumes", tags=["resume-audit"])
app.include_router(onboarding.router, prefix="/api/resumes", tags=["onboarding"])
app.include_router(vacancies.router, prefix="/api/vacancies", tags=["vacancies"])
app.include_router(track_gaps.router, prefix="/api", tags=["track-gaps"])
app.include_router(applications.router, prefix="/api/applications", tags=["applications"])
app.include_router(telemetry.router, prefix="/api/telemetry", tags=["telemetry"])
