"""add resume profiles

Revision ID: 0002_resume_profiles
Revises: 0001_initial
Create Date: 2026-04-16 19:45:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_resume_profiles"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resume_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("profile", sa.JSON(), nullable=False),
        sa.Column("canonical_text", sa.Text(), nullable=False),
        sa.Column("qdrant_collection", sa.String(length=255), nullable=False),
        sa.Column("qdrant_point_id", sa.String(length=64), nullable=False),
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("resume_id", name="uq_resume_profiles_resume_id"),
    )
    op.create_index("ix_resume_profiles_resume_id", "resume_profiles", ["resume_id"])
    op.create_index("ix_resume_profiles_user_id", "resume_profiles", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_resume_profiles_user_id", table_name="resume_profiles")
    op.drop_index("ix_resume_profiles_resume_id", table_name="resume_profiles")
    op.drop_table("resume_profiles")
