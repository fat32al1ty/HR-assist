"""Phase 2.7 — salary fields on vacancy_profiles + user expectations

Revision ID: 0021_salary_fields
Revises: 0020_match_telemetry
Create Date: 2026-04-22 15:00:00

Adds stated and (future-)predicted salary columns to ``vacancy_profiles``
and expected-salary preferences to ``users``. All columns are NULL-safe;
existing rows stay untouched until the backfill script runs.

The predicted_* columns are schema only — the LightGBM predictor in
``salary_predictor.py`` is a skeleton that returns None until the
corpus has enough RUB-priced training rows (plan target ≥10k; today
the corpus has ~64).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_salary_fields"
down_revision: Union[str, None] = "0020_match_telemetry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "vacancy_profiles",
        sa.Column("salary_min", sa.Integer(), nullable=True),
    )
    op.add_column(
        "vacancy_profiles",
        sa.Column("salary_max", sa.Integer(), nullable=True),
    )
    op.add_column(
        "vacancy_profiles",
        sa.Column("salary_currency", sa.String(length=3), nullable=True),
    )
    op.add_column(
        "vacancy_profiles",
        sa.Column("salary_gross", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "vacancy_profiles",
        sa.Column("predicted_salary_p25", sa.Integer(), nullable=True),
    )
    op.add_column(
        "vacancy_profiles",
        sa.Column("predicted_salary_p50", sa.Integer(), nullable=True),
    )
    op.add_column(
        "vacancy_profiles",
        sa.Column("predicted_salary_p75", sa.Integer(), nullable=True),
    )
    op.add_column(
        "vacancy_profiles",
        sa.Column("predicted_salary_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "vacancy_profiles",
        sa.Column(
            "predicted_salary_model_version",
            sa.String(length=32),
            nullable=True,
        ),
    )

    op.add_column(
        "users",
        sa.Column("expected_salary_min", sa.Integer(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("expected_salary_max", sa.Integer(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "expected_salary_currency",
            sa.String(length=3),
            nullable=False,
            server_default="RUB",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "expected_salary_currency")
    op.drop_column("users", "expected_salary_max")
    op.drop_column("users", "expected_salary_min")
    op.drop_column("vacancy_profiles", "predicted_salary_model_version")
    op.drop_column("vacancy_profiles", "predicted_salary_confidence")
    op.drop_column("vacancy_profiles", "predicted_salary_p75")
    op.drop_column("vacancy_profiles", "predicted_salary_p50")
    op.drop_column("vacancy_profiles", "predicted_salary_p25")
    op.drop_column("vacancy_profiles", "salary_gross")
    op.drop_column("vacancy_profiles", "salary_currency")
    op.drop_column("vacancy_profiles", "salary_max")
    op.drop_column("vacancy_profiles", "salary_min")
