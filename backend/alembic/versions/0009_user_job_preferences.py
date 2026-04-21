"""user job preferences: work format, relocation, home city, preferred titles

Revision ID: 0009_user_job_preferences
Revises: 0008_user_daily_spend
Create Date: 2026-04-21 16:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_user_job_preferences"
down_revision: Union[str, None] = "0008_user_daily_spend"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "preferred_work_format",
            sa.String(length=16),
            nullable=False,
            server_default="any",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "relocation_mode",
            sa.String(length=16),
            nullable=False,
            server_default="home_only",
        ),
    )
    op.add_column(
        "users",
        sa.Column("home_city", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "preferred_titles",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "preferred_titles")
    op.drop_column("users", "home_city")
    op.drop_column("users", "relocation_mode")
    op.drop_column("users", "preferred_work_format")
