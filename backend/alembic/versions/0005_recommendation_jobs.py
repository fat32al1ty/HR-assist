"""add recommendation jobs table

Revision ID: 0005_recommendation_jobs
Revises: 0004_user_vacancy_feedback
Create Date: 2026-04-17 15:30:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_recommendation_jobs"
down_revision: Union[str, None] = "0004_user_vacancy_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recommendation_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(length=64), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("openai_usage", sa.JSON(), nullable=True),
        sa.Column("matches", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_recommendation_jobs_user_id", "recommendation_jobs", ["user_id"])
    op.create_index("ix_recommendation_jobs_resume_id", "recommendation_jobs", ["resume_id"])
    op.create_index("ix_recommendation_jobs_status", "recommendation_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_recommendation_jobs_status", table_name="recommendation_jobs")
    op.drop_index("ix_recommendation_jobs_resume_id", table_name="recommendation_jobs")
    op.drop_index("ix_recommendation_jobs_user_id", table_name="recommendation_jobs")
    op.drop_table("recommendation_jobs")
