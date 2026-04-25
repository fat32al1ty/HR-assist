"""Add vacancy_strategies table

Revision ID: 0033_vacancy_strategies
Revises: 0032_application_track
Create Date: 2026-04-25 14:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033_vacancy_strategies"
down_revision: Union[str, None] = "0032_application_track"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index("ix_vs_resume_computed", table_name="vacancy_strategies")
    op.drop_table("vacancy_strategies")
