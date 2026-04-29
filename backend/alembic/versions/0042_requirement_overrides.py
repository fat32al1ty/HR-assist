"""requirement_overrides table

Revision ID: 0042_req_overrides
Revises: 0041_merge_heads
Create Date: 2026-04-29 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0042_req_overrides"
down_revision: Union[str, None] = "0041_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "requirement_overrides",
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
        sa.Column("section", sa.String(length=16), nullable=False),
        sa.Column("requirement_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "section IN ('must_have', 'nice_to_have')",
            name="ck_requirement_overrides_section",
        ),
        sa.CheckConstraint(
            "status IN ('ok', 'missing')",
            name="ck_requirement_overrides_status",
        ),
    )
    op.create_index(
        "ix_requirement_overrides_resume_id",
        "requirement_overrides",
        ["resume_id"],
    )
    op.create_index(
        "ix_requirement_overrides_vacancy_id",
        "requirement_overrides",
        ["vacancy_id"],
    )
    op.create_index(
        "uq_requirement_overrides_pair_section_text",
        "requirement_overrides",
        ["resume_id", "vacancy_id", "section", sa.text("lower(requirement_text)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_requirement_overrides_pair_section_text",
        table_name="requirement_overrides",
    )
    op.drop_index(
        "ix_requirement_overrides_vacancy_id", table_name="requirement_overrides"
    )
    op.drop_index(
        "ix_requirement_overrides_resume_id", table_name="requirement_overrides"
    )
    op.drop_table("requirement_overrides")
