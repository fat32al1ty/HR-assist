"""Metrics + observability layer (v0.23.0)

Revision ID: 0040_metrics_layer
Revises: 0039_drop_vs_tables
Create Date: 2026-04-29 00:00:00

Adds three persistent tables that back the new admin metrics dashboards
and Prometheus /metrics endpoint:

- openai_call_log — replaces stdout-only OPENAI_CALL JSON-line audit so we
  can SQL-query cost per DAU/model/request_id.
- match_event — captures POST /api/telemetry/event payloads that were
  previously accepted-and-dropped on the floor.
- freshness_sweep_log — history of nightly vacancy_freshness sweeps;
  before this only the latest run was kept in worker memory state.

All additive. No existing rows affected.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0040_metrics_layer"
down_revision: Union[str, None] = "0039_drop_vs_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "openai_call_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("extra", sa.JSON, nullable=True),
    )
    op.create_index("ix_openai_call_log_ts", "openai_call_log", ["ts"])
    op.create_index("ix_openai_call_log_user_ts", "openai_call_log", ["user_id", "ts"])

    op.create_table(
        "match_event",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
    )
    op.create_index("ix_match_event_user_ts", "match_event", ["user_id", "ts"])
    op.create_index("ix_match_event_event_ts", "match_event", ["event", "ts"])

    op.create_table(
        "freshness_sweep_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked", sa.Integer, nullable=False, server_default="0"),
        sa.Column("archived", sa.Integer, nullable=False, server_default="0"),
        sa.Column("stopped_early", sa.SmallInteger, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("freshness_sweep_log")
    op.drop_index("ix_match_event_event_ts", table_name="match_event")
    op.drop_index("ix_match_event_user_ts", table_name="match_event")
    op.drop_table("match_event")
    op.drop_index("ix_openai_call_log_user_ts", table_name="openai_call_log")
    op.drop_index("ix_openai_call_log_ts", table_name="openai_call_log")
    op.drop_table("openai_call_log")
