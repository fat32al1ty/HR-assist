"""Level A PII minimization — drop extracted_text, make storage_path nullable

Revision ID: 0023_pii_minimization
Revises: 0022_user_is_admin
Create Date: 2026-04-23 10:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023_pii_minimization"
down_revision: Union[str, None] = "0022_user_is_admin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("resumes", "extracted_text")
    op.alter_column("resumes", "storage_path", existing_type=sa.String(512), nullable=True)


def downgrade() -> None:
    op.alter_column("resumes", "storage_path", existing_type=sa.String(512), nullable=False, server_default="")
    op.execute("UPDATE resumes SET storage_path = '' WHERE storage_path IS NULL")
    op.add_column("resumes", sa.Column("extracted_text", sa.Text(), nullable=True))
