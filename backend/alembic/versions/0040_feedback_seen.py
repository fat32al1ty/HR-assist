"""Add seen column to user_vacancy_feedback

Revision ID: 0040_feedback_seen
Revises: 0039_drop_vs_tables
Create Date: 2026-04-29 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0040_feedback_seen"
down_revision: Union[str, None] = "0039_drop_vs_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_vacancy_feedback",
        sa.Column(
            "seen",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_vacancy_feedback", "seen")
