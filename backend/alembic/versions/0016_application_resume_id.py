"""applications: stamp resume_id for multi-profile Kanban badges

Revision ID: 0016_application_resume_id
Revises: 0015_resume_label
Create Date: 2026-04-21 23:45:00

Phase 1.7 PR #6 — the Kanban stays common across profiles, but each card
needs to show which resume it was created under. We store the user's
active resume_id at creation time. Nullable + ON DELETE SET NULL so a
deleted resume doesn't wipe the user's application history.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_application_resume_id"
down_revision: Union[str, None] = "0015_resume_label"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("resume_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_applications_resume",
        "applications",
        "resumes",
        ["resume_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_applications_resume_id", "applications", ["resume_id"])

    # Best-effort backfill: stamp the user's currently-active resume onto any
    # pre-existing applications so legacy Kanban cards display a badge too.
    op.execute(
        """
        UPDATE applications a
        SET resume_id = r.id
        FROM resumes r
        WHERE r.user_id = a.user_id
          AND r.is_active = true
          AND a.resume_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_applications_resume_id", table_name="applications")
    op.drop_constraint("fk_applications_resume", "applications", type_="foreignkey")
    op.drop_column("applications", "resume_id")
