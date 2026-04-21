"""resume label column for multi-profile UI

Revision ID: 0015_resume_label
Revises: 0014_multi_profile
Create Date: 2026-04-21 23:30:00

Adds a short user-editable label ("IC Staff", "Mgmt") shown on the profile
switcher and per-card badges. Nullable on purpose — until the user sets one,
the UI falls back to the original filename.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_resume_label"
down_revision: Union[str, None] = "0014_multi_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "resumes",
        sa.Column("label", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("resumes", "label")
