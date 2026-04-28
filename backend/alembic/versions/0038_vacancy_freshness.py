"""Add freshness tracking columns to vacancies

Revision ID: 0038_vacancy_freshness
Revises: 0037_segment_warmup_jobs
Create Date: 2026-04-28 00:00:00

Adds three columns to support on-read and nightly freshness checks (v0.22.0):
- last_freshness_check TIMESTAMPTZ NULL
- archived_at TIMESTAMPTZ NULL
- shown_count INTEGER NOT NULL DEFAULT 0
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0038_vacancy_freshness"
down_revision: Union[str, None] = "0037_segment_warmup_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "vacancies",
        sa.Column("last_freshness_check", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "vacancies",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "vacancies",
        sa.Column(
            "shown_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("vacancies", "shown_count")
    op.drop_column("vacancies", "archived_at")
    op.drop_column("vacancies", "last_freshness_check")
