"""Admin overview — add last_login_at to users

Revision ID: 0024_user_last_login_at
Revises: 0023_pii_minimization
Create Date: 2026-04-24 12:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024_user_last_login_at"
down_revision: Union[str, None] = "0023_pii_minimization"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "last_login_at")
