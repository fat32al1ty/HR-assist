"""applications tracker: per-vacancy follow-up state

Revision ID: 0011_applications
Revises: 0010_recommendation_job_cancel
Create Date: 2026-04-21 20:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_applications"
down_revision: Union[str, None] = "0010_recommendation_job_cancel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("vacancy_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("cover_letter_text", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("vacancy_title", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("vacancy_company", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_status_change_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_applications_user_id", "applications", ["user_id"])
    op.create_index("ix_applications_status", "applications", ["status"])
    op.create_index(
        "ix_applications_user_vacancy", "applications", ["user_id", "vacancy_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_applications_user_vacancy", table_name="applications")
    op.drop_index("ix_applications_status", table_name="applications")
    op.drop_index("ix_applications_user_id", table_name="applications")
    op.drop_table("applications")
