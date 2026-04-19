"""auth hardening fields and otp codes

Revision ID: 0007_auth_hardening
Revises: 0006_feedback_liked
Create Date: 2026-04-19 22:40:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_auth_hardening"
down_revision: Union[str, None] = "0006_feedback_liked"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "auth_otp_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("purpose", sa.String(length=48), nullable=False),
        sa.Column("challenge_id", sa.String(length=128), nullable=True),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("challenge_id", name="uq_auth_otp_codes_challenge_id"),
    )
    op.create_index("ix_auth_otp_codes_user_id", "auth_otp_codes", ["user_id"])
    op.create_index("ix_auth_otp_codes_email", "auth_otp_codes", ["email"])
    op.create_index("ix_auth_otp_codes_purpose", "auth_otp_codes", ["purpose"])
    op.create_index("ix_auth_otp_codes_challenge_id", "auth_otp_codes", ["challenge_id"])
    op.create_index("ix_auth_otp_codes_expires_at", "auth_otp_codes", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_auth_otp_codes_expires_at", table_name="auth_otp_codes")
    op.drop_index("ix_auth_otp_codes_challenge_id", table_name="auth_otp_codes")
    op.drop_index("ix_auth_otp_codes_purpose", table_name="auth_otp_codes")
    op.drop_index("ix_auth_otp_codes_email", table_name="auth_otp_codes")
    op.drop_index("ix_auth_otp_codes_user_id", table_name="auth_otp_codes")
    op.drop_table("auth_otp_codes")

    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "email_verified")
