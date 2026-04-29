"""Drop vacancy_strategies and recommendation_corrections tables

Revision ID: 0039_drop_vacancy_strategy_tables
Revises: 0038_vacancy_freshness
Create Date: 2026-04-29 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0039_drop_vs_tables"
down_revision: Union[str, None] = "0038_vacancy_freshness"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # recommendation_corrections references vacancy_strategies (logical FK) — drop first
    op.drop_index("ix_rc_user_created", table_name="recommendation_corrections")
    op.drop_index("ix_rc_resume_vacancy", table_name="recommendation_corrections")
    op.drop_table("recommendation_corrections")

    op.drop_index("ix_vs_resume_computed", table_name="vacancy_strategies")
    op.drop_table("vacancy_strategies")


def downgrade() -> None:
    op.create_table(
        "vacancy_strategies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("vacancy_id", sa.Integer(), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("strategy_json", sa.JSON(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("template_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "resume_id", "vacancy_id", "prompt_version", name="uq_vs_resume_vacancy_prompt"
        ),
    )
    op.create_index("ix_vs_resume_computed", "vacancy_strategies", ["resume_id", "computed_at"])

    op.create_table(
        "recommendation_corrections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
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
