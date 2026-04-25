"""Click + dwell endpoints for match telemetry (Phase 2.6).

Impressions are written server-side at the tail of
``match_vacancies_for_resume`` — there is no impression endpoint by
design so we capture exactly what we sent, not what the client claims
to have rendered.

Clicks and dwell come in from the frontend. Rate-limited per user so a
misbehaving client can't DoS the table.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User
from app.services.match_telemetry import (
    ALLOWED_CLICK_KINDS,
    log_click,
    log_dwell_batch,
)

CLICK_RATE_LIMIT = "120/minute"
DWELL_RATE_LIMIT = "60/minute"
EVENT_RATE_LIMIT = "120/minute"

ALLOWED_EVENT_NAMES = frozenset(
    {
        "track_section_expanded",
        "track_gap_clicked",
        "softer_subset_clicked",
        "apply_from_track",
        "strategy_view",
        "strategy_match_highlight_corrected",
        "strategy_gap_mitigation_corrected",
        "cover_letter_copied",
        "cover_letter_edited",
        "apply_after_strategy_view",
    }
)

router = APIRouter()


class ClickPayload(BaseModel):
    vacancy_id: int
    click_kind: str = Field(..., max_length=20)
    match_run_id: uuid.UUID | None = None
    resume_id: int | None = None
    position: int | None = None


class EventPayload(BaseModel):
    event: str = Field(..., max_length=64)
    payload: dict = Field(default_factory=dict)


class DwellRow(BaseModel):
    vacancy_id: int
    ms: int = Field(..., ge=0, le=60 * 60 * 1000)


class DwellPayload(BaseModel):
    match_run_id: uuid.UUID
    rows: list[DwellRow] = Field(default_factory=list, max_length=100)


@router.post("/click", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(CLICK_RATE_LIMIT)
def post_click(
    request: Request,
    response: Response,
    payload: ClickPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if payload.click_kind not in ALLOWED_CLICK_KINDS:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)
    log_click(
        db,
        user_id=current_user.id,
        resume_id=payload.resume_id,
        vacancy_id=payload.vacancy_id,
        match_run_id=payload.match_run_id,
        position=payload.position,
        click_kind=payload.click_kind,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/dwell", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(DWELL_RATE_LIMIT)
def post_dwell(
    request: Request,
    response: Response,
    payload: DwellPayload,
    current_user: User = Depends(get_current_user),  # noqa: ARG001 — auth gate only
    db: Session = Depends(get_db),
) -> Response:
    entries = [(row.vacancy_id, row.ms) for row in payload.rows if row.ms > 0]
    log_dwell_batch(db, match_run_id=payload.match_run_id, entries=entries)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/event", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(EVENT_RATE_LIMIT)
def post_event(
    request: Request,
    response: Response,
    payload: EventPayload,
    current_user: User = Depends(get_current_user),  # noqa: ARG001 — auth gate only
) -> Response:
    if payload.event not in ALLOWED_EVENT_NAMES:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
