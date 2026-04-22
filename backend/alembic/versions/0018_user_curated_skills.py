"""resume_user_skills: user-curated added/rejected skills

Revision ID: 0018_user_curated_skills
Revises: 0017_user_last_hh_seen_at
Create Date: 2026-04-22 00:30:00

Phase 1.9 PR C1 — user agency. Even after Track B (quant-detector +
taxonomy) the matcher will still be wrong sometimes. Give the user a
way to say "I have this" / "this isn't me", persisted per-resume, and
thread it into match scoring. This table holds both directions so the
UI can undo either polarity symmetrically.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018_user_curated_skills"
down_revision: str | None = "0017_user_last_hh_seen_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resume_user_skills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "resume_id",
            sa.Integer(),
            sa.ForeignKey("resumes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("skill_text", sa.Text(), nullable=False),
        sa.Column(
            "direction",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "source_vacancy_id",
            sa.Integer(),
            sa.ForeignKey("vacancies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "direction IN ('added', 'rejected')",
            name="ck_resume_user_skills_direction",
        ),
    )
    # Case-insensitive uniqueness: typing "Kubernetes" then "kubernetes"
    # must be treated as a single row, not two — otherwise the UI
    # dedup becomes a fragile consumer-side concern.
    op.create_index(
        "idx_resume_user_skills_unique",
        "resume_user_skills",
        ["resume_id", sa.text("LOWER(skill_text)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_resume_user_skills_unique", table_name="resume_user_skills")
    op.drop_table("resume_user_skills")
