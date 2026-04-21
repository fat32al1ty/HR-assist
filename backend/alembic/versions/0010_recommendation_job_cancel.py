"""recommendation jobs: cancel_requested flag

Revision ID: 0010_recommendation_job_cancel
Revises: 0009_user_job_preferences
Create Date: 2026-04-21 19:30:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_recommendation_job_cancel"
down_revision: Union[str, None] = "0009_user_job_preferences"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recommendation_jobs",
        sa.Column(
            "cancel_requested",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("recommendation_jobs", "cancel_requested")
