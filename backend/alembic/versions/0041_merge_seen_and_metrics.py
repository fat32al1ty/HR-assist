"""merge feedback_seen and metrics_layer heads

Revision ID: 0041_merge_heads
Revises: 0040_feedback_seen, 0040_metrics_layer
Create Date: 2026-04-29 00:00:00
"""

from typing import Sequence, Union

revision: str = "0041_merge_heads"
down_revision: Union[str, Sequence[str], None] = (
    "0040_feedback_seen",
    "0040_metrics_layer",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
