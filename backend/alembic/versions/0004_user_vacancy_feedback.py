"""add user vacancy feedback table

Revision ID: 0004_user_vacancy_feedback
Revises: 0003_vacancies
Create Date: 2026-04-17 01:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_user_vacancy_feedback"
down_revision: Union[str, None] = "0003_vacancies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_vacancy_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("vacancy_id", sa.Integer(), nullable=False),
        sa.Column("disliked", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "vacancy_id", name="uq_user_vacancy_feedback"),
    )
    op.create_index("ix_user_vacancy_feedback_user_id", "user_vacancy_feedback", ["user_id"])
    op.create_index("ix_user_vacancy_feedback_vacancy_id", "user_vacancy_feedback", ["vacancy_id"])


def downgrade() -> None:
    op.drop_index("ix_user_vacancy_feedback_vacancy_id", table_name="user_vacancy_feedback")
    op.drop_index("ix_user_vacancy_feedback_user_id", table_name="user_vacancy_feedback")
    op.drop_table("user_vacancy_feedback")
