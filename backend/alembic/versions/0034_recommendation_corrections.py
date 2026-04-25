"""Add recommendation_corrections table

Revision ID: 0034_recommendation_corrections
Revises: 0033_vacancy_strategies
Create Date: 2026-04-25 15:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0034_recommendation_corrections"
down_revision: Union[str, None] = "0033_vacancy_strategies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recommendation_corrections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "resume_id",
            sa.Integer(),
            sa.ForeignKey("resumes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "vacancy_id",
            sa.Integer(),
            sa.ForeignKey("vacancies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("correction_type", sa.String(32), nullable=False),
        sa.Column("subject_index", sa.Integer(), nullable=False),
        sa.Column("subject_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_rc_resume_vacancy", "recommendation_corrections", ["resume_id", "vacancy_id"]
    )
    op.create_index(
        "ix_rc_user_created", "recommendation_corrections", ["user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_rc_user_created", table_name="recommendation_corrections")
    op.drop_index("ix_rc_resume_vacancy", table_name="recommendation_corrections")
    op.drop_table("recommendation_corrections")
