"""add vacancies and vacancy profiles

Revision ID: 0003_vacancies
Revises: 0002_resume_profiles
Create Date: 2026-04-16 20:20:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_vacancies"
down_revision: Union[str, None] = "0002_resume_profiles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vacancies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="indexed"),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source_url", name="uq_vacancies_source_url"),
    )
    op.create_index("ix_vacancies_source", "vacancies", ["source"])
    op.create_index("ix_vacancies_source_url", "vacancies", ["source_url"])
    op.create_index("ix_vacancies_status", "vacancies", ["status"])

    op.create_table(
        "vacancy_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vacancy_id", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("profile", sa.JSON(), nullable=False),
        sa.Column("canonical_text", sa.Text(), nullable=False),
        sa.Column("qdrant_collection", sa.String(length=255), nullable=False),
        sa.Column("qdrant_point_id", sa.String(length=64), nullable=False),
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("vacancy_id", name="uq_vacancy_profiles_vacancy_id"),
    )
    op.create_index("ix_vacancy_profiles_vacancy_id", "vacancy_profiles", ["vacancy_id"])


def downgrade() -> None:
    op.drop_index("ix_vacancy_profiles_vacancy_id", table_name="vacancy_profiles")
    op.drop_table("vacancy_profiles")
    op.drop_index("ix_vacancies_status", table_name="vacancies")
    op.drop_index("ix_vacancies_source_url", table_name="vacancies")
    op.drop_index("ix_vacancies_source", table_name="vacancies")
    op.drop_table("vacancies")
