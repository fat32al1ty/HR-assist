"""multi-profile: scope feedback to resume_id, mark exactly one active resume per user

Revision ID: 0014_multi_profile
Revises: 0013_blocked_hosts_cleanup
Create Date: 2026-04-21 23:00:00

Phase 1.7 Track B — makes every liked/disliked row provably belong to a
particular resume so senior users juggling two career tracks (IC vs Mgmt)
get isolated preference centroids. Each user gets exactly one is_active=true
resume at a time, enforced by a partial unique index.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_multi_profile"
down_revision: Union[str, None] = "0013_blocked_hosts_cleanup"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "resumes",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Activate the most-recently-created resume per user so the new invariant
    # ("exactly one active resume") is satisfied before we add the unique index.
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY user_id
                       ORDER BY created_at DESC, id DESC
                   ) AS rn
            FROM resumes
        )
        UPDATE resumes
        SET is_active = true
        FROM ranked
        WHERE resumes.id = ranked.id AND ranked.rn = 1
        """
    )

    op.create_index(
        "uq_resumes_one_active_per_user",
        "resumes",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.add_column(
        "user_vacancy_feedback",
        sa.Column("resume_id", sa.Integer(), nullable=True),
    )

    # Backfill: every existing feedback row gets pinned to the user's currently
    # active resume. Orphans (user with feedback but no resume) cannot exist
    # under the current data model, but be defensive and delete them so the
    # NOT NULL flip is safe.
    op.execute(
        """
        UPDATE user_vacancy_feedback f
        SET resume_id = r.id
        FROM resumes r
        WHERE r.user_id = f.user_id AND r.is_active = true
        """
    )
    op.execute("DELETE FROM user_vacancy_feedback WHERE resume_id IS NULL")

    op.alter_column("user_vacancy_feedback", "resume_id", nullable=False)
    op.create_foreign_key(
        "fk_user_vacancy_feedback_resume",
        "user_vacancy_feedback",
        "resumes",
        ["resume_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_user_vacancy_feedback_resume_id",
        "user_vacancy_feedback",
        ["resume_id"],
    )

    op.drop_constraint("uq_user_vacancy_feedback", "user_vacancy_feedback", type_="unique")
    op.create_unique_constraint(
        "uq_user_vacancy_feedback",
        "user_vacancy_feedback",
        ["user_id", "resume_id", "vacancy_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_user_vacancy_feedback", "user_vacancy_feedback", type_="unique")
    op.create_unique_constraint(
        "uq_user_vacancy_feedback",
        "user_vacancy_feedback",
        ["user_id", "vacancy_id"],
    )
    op.drop_index("ix_user_vacancy_feedback_resume_id", table_name="user_vacancy_feedback")
    op.drop_constraint(
        "fk_user_vacancy_feedback_resume", "user_vacancy_feedback", type_="foreignkey"
    )
    op.drop_column("user_vacancy_feedback", "resume_id")
    op.drop_index("uq_resumes_one_active_per_user", table_name="resumes")
    op.drop_column("resumes", "is_active")
