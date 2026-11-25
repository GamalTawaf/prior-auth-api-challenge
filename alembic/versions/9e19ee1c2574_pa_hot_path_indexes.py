"""pa hot path indexes

Revision ID: 9e19ee1c2574
Revises: ac515227436d
Create Date: 2026-11-25 10:17:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "9e19ee1c2574"
down_revision: Union[str, None] = "ac515227436d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_pa_member_created",
        "prior_auth_requests",
        ["member_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_pa_practice_created",
        "prior_auth_requests",
        ["practice_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pa_practice_created", table_name="prior_auth_requests")
    op.drop_index("ix_pa_member_created", table_name="prior_auth_requests")
