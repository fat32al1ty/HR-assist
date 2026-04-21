"""applications: track when cover letter was generated for 24h cooldown

Revision ID: 0012_cover_letter_stamp
Revises: 0011_applications
Create Date: 2026-04-21 21:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_cover_letter_stamp"
down_revision: Union[str, None] = "0011_applications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("cover_letter_generated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("applications", "cover_letter_generated_at")
