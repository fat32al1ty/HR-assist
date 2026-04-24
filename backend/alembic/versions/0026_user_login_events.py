"""Add user_login_events table for per-day activity statistics

Revision ID: 0026_user_login_events
Revises: 0025_user_vacancy_seen
Create Date: 2026-04-24 14:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_user_login_events"
down_revision: Union[str, None] = "0025_user_vacancy_seen"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_login_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_user_login_events_user_occurred",
        "user_login_events",
        ["user_id", "occurred_at"],
    )
    op.create_index(
        "ix_user_login_events_occurred",
        "user_login_events",
        ["occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_login_events_occurred", table_name="user_login_events")
    op.drop_index("ix_user_login_events_user_occurred", table_name="user_login_events")
    op.drop_table("user_login_events")
