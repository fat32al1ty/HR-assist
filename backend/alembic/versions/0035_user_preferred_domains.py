"""Add preferred_domains column to users table

Revision ID: 0035_user_preferred_domains
Revises: 0034_recommendation_corrections
Create Date: 2026-04-28 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "0035_user_preferred_domains"
down_revision: Union[str, None] = "0034_recommendation_corrections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "preferred_domains",
            ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    # Backfill existing rows (server_default only fires on INSERT, not UPDATE)
    op.execute("UPDATE users SET preferred_domains = '{}' WHERE preferred_domains IS NULL")


def downgrade() -> None:
    op.drop_column("users", "preferred_domains")
