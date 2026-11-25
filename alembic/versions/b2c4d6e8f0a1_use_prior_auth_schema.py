"""Move application tables into the prior_auth schema.

Revision ID: b2c4d6e8f0a1
Revises: ac515227436d
Create Date: 2026-11-25 11:25:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b2c4d6e8f0a1"
down_revision: Union[str, None] = "ac515227436d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_SCHEMA = "prior_auth"

# Order: dependents before parents when moving back; forward uses IF EXISTS.
_TABLES = (
    "audit_events",
    "intake_rejections",
    "prior_auth_procedures",
    "prior_auth_requests",
    "reviewer_member_conflicts",
    "patient_practice_links",
    "coverages",
    "users",
    "members",
    "practices",
)


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {APP_SCHEMA}")
    for table in _TABLES:
        op.execute(f"ALTER TABLE IF EXISTS public.{table} SET SCHEMA {APP_SCHEMA}")


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE IF EXISTS {APP_SCHEMA}.{table} SET SCHEMA public")
    op.execute(f"DROP SCHEMA IF EXISTS {APP_SCHEMA}")
