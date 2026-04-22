"""users: last_hh_seen_at cursor for incremental HH fetch

Revision ID: 0017_user_last_hh_seen_at
Revises: 0016_application_resume_id
Create Date: 2026-04-21 23:50:00

Phase 1.9 PR A1 — the HH pipeline was re-scanning the same ~40 top
results on every /recommend call, because we never told the HH API
"only items newer than X". Store the last successful fetch timestamp
per user so subsequent calls pass `date_from` and surface genuinely
new vacancies.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_user_last_hh_seen_at"
down_revision: Union[str, None] = "0016_application_resume_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "last_hh_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "last_hh_seen_at")
