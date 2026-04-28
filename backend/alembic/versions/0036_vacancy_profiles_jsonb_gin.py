"""Add functional GIN index on vacancy_profiles.profile cast to jsonb

Revision ID: 0036_vacancy_profiles_jsonb_gin
Revises: 0035_user_preferred_domains
Create Date: 2026-04-28 00:00:00

The /api/users/preferences/suggestions endpoint queries vacancy_profiles
by JSONB key existence and array membership against `profile::jsonb`. The
column type is `json` (legacy), so each row is cast on the fly. Without
an index the query is a full table scan on every typeahead miss.

A functional GIN index on `(profile::jsonb)` lets PostgreSQL use the
index for the `?` and `@>` operators on the cast expression. Cheaper
than migrating the column type to jsonb (which would take an exclusive
lock on a populated production table).

The index is created CONCURRENTLY so we don't block writes; the migration
must run outside a transaction (autocommit_block).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0036_vacancy_profiles_jsonb_gin"
down_revision: Union[str, None] = "0035_user_preferred_domains"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_vacancy_profiles_profile_jsonb "
            "ON vacancy_profiles USING GIN ((profile::jsonb))"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_vacancy_profiles_profile_jsonb")
