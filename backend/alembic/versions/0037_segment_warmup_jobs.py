"""Add job_type, segment_key, notify_user_id to recommendation_jobs

Revision ID: 0037_segment_warmup_jobs
Revises: 0036_vacancy_profiles_jsonb_gin
Create Date: 2026-04-28 00:00:00

Adds three columns to support lazy segment-warmup jobs (v0.21.0):
- job_type VARCHAR(32) NOT NULL DEFAULT 'deep_scan'
- segment_key VARCHAR(64) NULL
- notify_user_id INTEGER NULL FK -> users.id ON DELETE SET NULL

Also adds a unique partial index on (segment_key) WHERE status IN
('queued', 'running') AND segment_key IS NOT NULL so that concurrent
enqueue calls for the same segment are idempotent at the DB level.

Postgres-only partial index: SQLite does not support partial indexes but
is not in the test or prod path (DATABASE_URL always targets PostgreSQL).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0037_segment_warmup_jobs"
down_revision: Union[str, None] = "0036_vacancy_profiles_jsonb_gin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recommendation_jobs",
        sa.Column(
            "job_type",
            sa.String(32),
            nullable=False,
            server_default="deep_scan",
        ),
    )
    op.add_column(
        "recommendation_jobs",
        sa.Column("segment_key", sa.String(64), nullable=True),
    )
    op.add_column(
        "recommendation_jobs",
        sa.Column(
            "notify_user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Backfill existing rows: server_default handles new rows; this covers rows
    # inserted between DDL execution and the constraint taking effect.
    op.execute(
        "UPDATE recommendation_jobs SET job_type = 'deep_scan' WHERE job_type IS NULL"
    )

    # Unique partial index — Postgres only (SQLite not in prod/test path).
    op.execute(
        "CREATE UNIQUE INDEX ix_recommendation_jobs_segment_key_active "
        "ON recommendation_jobs (segment_key) "
        "WHERE status IN ('queued', 'running') AND segment_key IS NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS ix_recommendation_jobs_segment_key_active"
    )
    op.drop_column("recommendation_jobs", "notify_user_id")
    op.drop_column("recommendation_jobs", "segment_key")
    op.drop_column("recommendation_jobs", "job_type")
