"""Level 2 D2 — user_vacancy_seen dedup table

Revision ID: 0025_user_vacancy_seen
Revises: 0024_user_last_login_at
Create Date: 2026-04-24 13:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025_user_vacancy_seen"
down_revision: Union[str, None] = "0024_user_last_login_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_vacancy_seen",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "vacancy_id",
            sa.Integer(),
            sa.ForeignKey("vacancies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "shown_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "vacancy_id", name="uq_user_vacancy_seen"),
    )
    op.create_index(
        "ix_user_vacancy_seen_user_id", "user_vacancy_seen", ["user_id"]
    )
    op.create_index(
        "ix_user_vacancy_seen_vacancy_id", "user_vacancy_seen", ["vacancy_id"]
    )
    op.create_index(
        "ix_user_vacancy_seen_user_shown",
        "user_vacancy_seen",
        ["user_id", "shown_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_vacancy_seen_user_shown", table_name="user_vacancy_seen")
    op.drop_index("ix_user_vacancy_seen_vacancy_id", table_name="user_vacancy_seen")
    op.drop_index("ix_user_vacancy_seen_user_id", table_name="user_vacancy_seen")
    op.drop_table("user_vacancy_seen")
