"""add domain check constraints

Revision ID: c7f3a91e2b04
Revises: ac515227436d
Create Date: 2026-11-25 10:20:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c7f3a91e2b04"
down_revision: Union[str, None] = "ac515227436d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_decided_requires_timestamp",
        "prior_auth_requests",
        "(status <> 'decided') OR (decided_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_in_review_requires_claimant",
        "prior_auth_requests",
        "(status <> 'in_review') OR (claimed_by_user_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_procedure_units_at_least_one",
        "prior_auth_procedures",
        "units >= 1",
    )
    op.create_check_constraint(
        "ck_denied_requires_reason",
        "prior_auth_procedures",
        "(decision <> 'denied') OR (denial_reason IS NOT NULL AND btrim(denial_reason) <> '')",
    )
    op.create_check_constraint(
        "ck_member_role_requires_member_id",
        "users",
        "(role <> 'member') OR (member_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_member_role_requires_member_id", "users", type_="check")
    op.drop_constraint("ck_denied_requires_reason", "prior_auth_procedures", type_="check")
    op.drop_constraint("ck_procedure_units_at_least_one", "prior_auth_procedures", type_="check")
    op.drop_constraint("ck_in_review_requires_claimant", "prior_auth_requests", type_="check")
    op.drop_constraint("ck_decided_requires_timestamp", "prior_auth_requests", type_="check")
