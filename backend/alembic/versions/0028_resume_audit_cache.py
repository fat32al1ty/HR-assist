"""Add resume_audits cache table

Revision ID: 0028_resume_audit_cache
Revises: 0027_resume_vacancy_scores
Create Date: 2026-04-25 10:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028_resume_audit_cache"
down_revision: Union[str, None] = "0027_resume_vacancy_scores"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resume_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "resume_id",
            sa.Integer(),
            sa.ForeignKey("resumes.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("audit_json", sa.JSON(), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.UniqueConstraint("resume_id", name="uq_resume_audits_resume_id"),
    )
    op.create_index("ix_resume_audits_resume_id", "resume_audits", ["resume_id"])


def downgrade() -> None:
    op.drop_index("ix_resume_audits_resume_id", table_name="resume_audits")
    op.drop_table("resume_audits")
