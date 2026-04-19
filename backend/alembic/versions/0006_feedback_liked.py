"""add liked flag to user vacancy feedback

Revision ID: 0006_feedback_liked
Revises: 0005_recommendation_jobs
Create Date: 2026-04-17 16:05:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_feedback_liked"
down_revision: Union[str, None] = "0005_recommendation_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_vacancy_feedback",
        sa.Column("liked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("user_vacancy_feedback", "liked")
