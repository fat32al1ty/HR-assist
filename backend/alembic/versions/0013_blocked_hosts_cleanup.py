"""vacancies: sweep previously-indexed rows from blocked hosts

Revision ID: 0013_blocked_hosts_cleanup
Revises: 0012_cover_letter_stamp
Create Date: 2026-04-21 22:00:00

Phase 1.7 index hygiene: djinni.co and workingnomads.com are non-target
sources that `_host_allowed_for_matching` already filters out at match
time. Historical vacancies indexed before that filter was tightened still
take up `status='indexed'` rows, skewing metrics and wasting Qdrant K.
Flip them to `status='filtered'` so downstream queries stop counting
them as viable matches.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0013_blocked_hosts_cleanup"
down_revision: Union[str, None] = "0012_cover_letter_stamp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BLOCKED_HOST_FRAGMENTS = (
    "djinni.co",
    "workingnomads.com",
)


def upgrade() -> None:
    for fragment in BLOCKED_HOST_FRAGMENTS:
        op.execute(
            """
            UPDATE vacancies
            SET status = 'filtered',
                error_message = 'blocked host (""" + fragment + """)'
            WHERE status = 'indexed'
              AND source_url ILIKE '%""" + fragment + """%'
            """
        )


def downgrade() -> None:
    # No automatic rollback: we do not track the pre-migration status of
    # each row. Manual re-indexing is the path back if this is ever wrong.
    pass
