"""Create track_gap_analyses table

Revision ID: 0031_track_gap_analyses
Revises: 0030_resume_vacancy_score_track
Create Date: 2026-04-25 12:05:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031_track_gap_analyses"
down_revision: Union[str, None] = "0030_resume_vacancy_score_track"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "track_gap_analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "resume_id",
            sa.Integer(),
            sa.ForeignKey("resumes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("analysis_json", sa.JSON(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("resume_id", name="uq_tga_resume"),
    )


def downgrade() -> None:
    op.drop_table("track_gap_analyses")
