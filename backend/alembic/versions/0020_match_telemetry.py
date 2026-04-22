"""match_impression / match_click / match_dwell telemetry tables

Revision ID: 0020_match_telemetry
Revises: 0019_esco_tables
Create Date: 2026-04-22 03:00:00

Phase 2.6 — append-only telemetry foundation for Learning-to-Rank.
Every match response stamps a ``match_run_id`` and bulk-inserts one
``match_impression`` row per visible card. Clicks and dwell come in
later from the frontend via ``/api/telemetry/*`` endpoints.

Indexes are minimal on purpose: PK + (user_id, ts) for user-scoped
scans + ts for global range scans. Partitioning is deferred — revisit
past 10M rows.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0020_match_telemetry"
down_revision: str | None = "0019_esco_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "match_impression",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
        sa.Column("match_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(length=10), nullable=False),
        sa.Column("vector_score", sa.Float(), nullable=True),
        sa.Column("hybrid_score", sa.Float(), nullable=True),
        sa.Column("rerank_score", sa.Float(), nullable=True),
        sa.Column("llm_confidence", sa.Float(), nullable=True),
        sa.Column("role_family", sa.String(length=40), nullable=True),
    )
    op.create_index(
        "idx_match_impression_user_ts",
        "match_impression",
        ["user_id", "ts"],
    )
    op.create_index(
        "idx_match_impression_run",
        "match_impression",
        ["match_run_id"],
    )

    op.create_table(
        "match_click",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "resume_id",
            sa.Integer(),
            sa.ForeignKey("resumes.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "vacancy_id",
            sa.Integer(),
            sa.ForeignKey("vacancies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("match_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("click_kind", sa.String(length=20), nullable=False),
        sa.CheckConstraint(
            "click_kind IN ('open_card', 'open_source', 'apply', 'like', 'dislike')",
            name="ck_match_click_kind",
        ),
    )
    op.create_index(
        "idx_match_click_user_ts",
        "match_click",
        ["user_id", "ts"],
    )
    op.create_index(
        "idx_match_click_run",
        "match_click",
        ["match_run_id"],
    )

    op.create_table(
        "match_dwell",
        sa.Column(
            "match_run_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "vacancy_id",
            sa.Integer(),
            sa.ForeignKey("vacancies.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("ms", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("match_dwell")
    op.drop_index("idx_match_click_run", table_name="match_click")
    op.drop_index("idx_match_click_user_ts", table_name="match_click")
    op.drop_table("match_click")
    op.drop_index("idx_match_impression_run", table_name="match_impression")
    op.drop_index("idx_match_impression_user_ts", table_name="match_impression")
    op.drop_table("match_impression")
