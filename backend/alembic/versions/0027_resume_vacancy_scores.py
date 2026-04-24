"""Add resume_vacancy_scores cache table

Revision ID: 0027_resume_vacancy_scores
Revises: 0026_user_login_events
Create Date: 2026-04-24 15:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027_resume_vacancy_scores"
down_revision: Union[str, None] = "0026_user_login_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resume_vacancy_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
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
        sa.Column("pipeline_version", sa.String(32), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("vector_score", sa.Float(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("scores_json", sa.JSON(), nullable=True),
        sa.UniqueConstraint(
            "resume_id",
            "vacancy_id",
            "pipeline_version",
            name="uq_rvs_resume_vacancy_pipeline",
        ),
    )
    op.create_index(
        "ix_rvs_resume_computed",
        "resume_vacancy_scores",
        ["resume_id", "computed_at"],
    )
    op.create_index(
        "ix_rvs_vacancy",
        "resume_vacancy_scores",
        ["vacancy_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_rvs_vacancy", table_name="resume_vacancy_scores")
    op.drop_index("ix_rvs_resume_computed", table_name="resume_vacancy_scores")
    op.drop_table("resume_vacancy_scores")
