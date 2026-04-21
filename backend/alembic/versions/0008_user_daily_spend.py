"""daily per-user OpenAI spend counter

Revision ID: 0008_user_daily_spend
Revises: 0007_auth_hardening
Create Date: 2026-04-21 12:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_user_daily_spend"
down_revision: Union[str, None] = "0007_auth_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_daily_spend",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "spend_usd",
            sa.Numeric(12, 6),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "date", name="uq_user_daily_spend_user_date"),
    )
    op.create_index("ix_user_daily_spend_user_id", "user_daily_spend", ["user_id"])
    op.create_index("ix_user_daily_spend_date", "user_daily_spend", ["date"])


def downgrade() -> None:
    op.drop_index("ix_user_daily_spend_date", table_name="user_daily_spend")
    op.drop_index("ix_user_daily_spend_user_id", table_name="user_daily_spend")
    op.drop_table("user_daily_spend")
