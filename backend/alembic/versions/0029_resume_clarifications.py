"""Add resume_clarifications table

Revision ID: 0029_resume_clarifications
Revises: 0028_resume_audit_cache
Create Date: 2026-04-25 10:05:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029_resume_clarifications"
down_revision: Union[str, None] = "0028_resume_audit_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resume_clarifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "resume_id",
            sa.Integer(),
            sa.ForeignKey("resumes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_id", sa.String(64), nullable=False),
        sa.Column("answer_value", sa.Text(), nullable=True),
        sa.Column(
            "answered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "resume_id",
            "question_id",
            name="uq_resume_clarifications_resume_question",
        ),
    )
    op.create_index(
        "ix_resume_clarifications_resume_id", "resume_clarifications", ["resume_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_resume_clarifications_resume_id", table_name="resume_clarifications")
    op.drop_table("resume_clarifications")
