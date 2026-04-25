"""Add track column to applications

Revision ID: 0032_application_track
Revises: 0031_track_gap_analyses
Create Date: 2026-04-25 13:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032_application_track"
down_revision: Union[str, None] = "0031_track_gap_analyses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("track", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("applications", "track")
