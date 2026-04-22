"""Phase 2.8 — add is_admin flag to users

Revision ID: 0022_user_is_admin
Revises: 0021_salary_fields
Create Date: 2026-04-22 16:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_user_is_admin"
down_revision: Union[str, None] = "0021_salary_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.execute("UPDATE users SET is_admin = true WHERE email = 'fat32al1ty@gmail.com'")


def downgrade() -> None:
    op.drop_column("users", "is_admin")
