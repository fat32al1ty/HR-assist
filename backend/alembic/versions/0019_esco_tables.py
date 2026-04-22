"""esco_* reference tables for occupations + skills

Revision ID: 0019_esco_tables
Revises: 0018_user_curated_skills
Create Date: 2026-04-22 01:15:00

Phase 2.4a — replace hand-curated alias groups with the EU's ESCO
taxonomy (Creative Commons BY 4.0). Four reference tables, populated
by a one-shot CSV import from the ESCO v1.1 dump. See docs/ESCO.md
for data source + refresh cadence.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0019_esco_tables"
down_revision: str | None = "0018_user_curated_skills"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "esco_occupation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("esco_uri", sa.String(length=255), nullable=False, unique=True, index=True),
        sa.Column("preferred_label_ru", sa.Text(), nullable=True),
        sa.Column("preferred_label_en", sa.Text(), nullable=False),
        sa.Column(
            "alt_labels_ru",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "alt_labels_en",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("isco_group", sa.String(length=16), nullable=True, index=True),
        sa.Column(
            "broader_occupation_id",
            sa.Integer(),
            sa.ForeignKey("esco_occupation.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.create_table(
        "esco_skill",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("esco_uri", sa.String(length=255), nullable=False, unique=True, index=True),
        sa.Column("preferred_label_ru", sa.Text(), nullable=True),
        sa.Column("preferred_label_en", sa.Text(), nullable=False),
        sa.Column(
            "alt_labels",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("reuse_level", sa.String(length=40), nullable=True),
        sa.Column("skill_type", sa.String(length=40), nullable=True),
    )

    op.create_table(
        "esco_occupation_skill",
        sa.Column(
            "occupation_id",
            sa.Integer(),
            sa.ForeignKey("esco_occupation.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "skill_id",
            sa.Integer(),
            sa.ForeignKey("esco_skill.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("relation", sa.String(length=20), primary_key=True),
        sa.CheckConstraint(
            "relation IN ('essential', 'optional')",
            name="ck_esco_occupation_skill_relation",
        ),
    )
    op.create_index(
        "idx_esco_occ_skill_skill",
        "esco_occupation_skill",
        ["skill_id"],
    )

    op.create_table(
        "esco_skill_relation",
        sa.Column(
            "from_id",
            sa.Integer(),
            sa.ForeignKey("esco_skill.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "to_id",
            sa.Integer(),
            sa.ForeignKey("esco_skill.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("relation", sa.String(length=20), primary_key=True),
        sa.CheckConstraint(
            "relation IN ('broader', 'narrower')",
            name="ck_esco_skill_relation_kind",
        ),
    )


def downgrade() -> None:
    op.drop_table("esco_skill_relation")
    op.drop_index("idx_esco_occ_skill_skill", table_name="esco_occupation_skill")
    op.drop_table("esco_occupation_skill")
    op.drop_table("esco_skill")
    op.drop_table("esco_occupation")
