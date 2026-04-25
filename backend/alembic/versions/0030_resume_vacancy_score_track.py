"""Add track column to resume_vacancy_scores

Revision ID: 0030_resume_vacancy_score_track
Revises: 0029_resume_clarifications
Create Date: 2026-04-25 12:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030_resume_vacancy_score_track"
down_revision: Union[str, None] = "0029_resume_clarifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "resume_vacancy_scores",
        sa.Column("track", sa.String(16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("resume_vacancy_scores", "track")
