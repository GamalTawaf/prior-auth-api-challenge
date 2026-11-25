"""Create prior_auth schema and all application tables.

Revision ID: 20261125_prior_auth
Revises:
Create Date: 2026-11-25 11:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261125_prior_auth"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "prior_auth"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    op.create_table(
        "members",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        schema=SCHEMA,
    )
    op.create_table(
        "practices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_table(
        "coverages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.Column("payer_name", sa.String(length=255), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["member_id"], [f"{SCHEMA}.members.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_coverages_member_id"),
        "coverages",
        ["member_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_table(
        "patient_practice_links",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.Column("practice_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], [f"{SCHEMA}.members.id"]),
        sa.ForeignKeyConstraint(["practice_id"], [f"{SCHEMA}.practices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id", "practice_id", name="uq_member_practice"),
        schema=SCHEMA,
    )
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "provider_office",
                "reviewer",
                "ops_admin",
                "member",
                name="user_role",
            ),
            nullable=False,
        ),
        sa.Column("practice_id", sa.UUID(), nullable=True),
        sa.Column("member_id", sa.UUID(), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["member_id"], [f"{SCHEMA}.members.id"]),
        sa.ForeignKeyConstraint(["practice_id"], [f"{SCHEMA}.practices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        schema=SCHEMA,
    )
    op.create_table(
        "intake_rejections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=False),
        sa.Column("practice_id", sa.UUID(), nullable=False),
        sa.Column(
            "at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("payload_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("field_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], [f"{SCHEMA}.users.id"]),
        sa.ForeignKeyConstraint(["practice_id"], [f"{SCHEMA}.practices.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_intake_rejections_correlation_id"),
        "intake_rejections",
        ["correlation_id"],
        unique=True,
        schema=SCHEMA,
    )
    op.create_table(
        "prior_auth_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.Column("practice_id", sa.UUID(), nullable=False),
        sa.Column("submitted_by_user_id", sa.UUID(), nullable=False),
        sa.Column("diagnosis_icd10", sa.String(length=16), nullable=False),
        sa.Column("date_of_service", sa.Date(), nullable=False),
        sa.Column("clinical_note", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "submitted",
                "in_review",
                "decided",
                name="request_status",
            ),
            nullable=False,
        ),
        sa.Column("claimed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_user_id", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status <> 'decided') OR (decided_by_user_id IS NOT NULL)",
            name="ck_decided_requires_actor",
        ),
        sa.ForeignKeyConstraint(["claimed_by_user_id"], [f"{SCHEMA}.users.id"]),
        sa.ForeignKeyConstraint(["decided_by_user_id"], [f"{SCHEMA}.users.id"]),
        sa.ForeignKeyConstraint(["member_id"], [f"{SCHEMA}.members.id"]),
        sa.ForeignKeyConstraint(["practice_id"], [f"{SCHEMA}.practices.id"]),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], [f"{SCHEMA}.users.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_pa_queue",
        "prior_auth_requests",
        ["status", "claimed_by_user_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_table(
        "reviewer_member_conflicts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("reviewer_user_id", sa.UUID(), nullable=False),
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], [f"{SCHEMA}.members.id"]),
        sa.ForeignKeyConstraint(["reviewer_user_id"], [f"{SCHEMA}.users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reviewer_user_id", "member_id", name="uq_reviewer_member_coi"),
        schema=SCHEMA,
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("request_id", sa.UUID(), nullable=True),
        sa.Column("intake_rejection_id", sa.UUID(), nullable=True),
        sa.Column("actor_user_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column(
            "at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], [f"{SCHEMA}.users.id"]),
        sa.ForeignKeyConstraint(["intake_rejection_id"], [f"{SCHEMA}.intake_rejections.id"]),
        sa.ForeignKeyConstraint(["request_id"], [f"{SCHEMA}.prior_auth_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_audit_events_request_id"),
        "audit_events",
        ["request_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_table(
        "prior_auth_procedures",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "decision",
            sa.Enum(
                "pending",
                "approved",
                "denied",
                name="procedure_decision",
            ),
            nullable=False,
        ),
        sa.Column("denial_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], [f"{SCHEMA}.prior_auth_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_prior_auth_procedures_request_id"),
        "prior_auth_procedures",
        ["request_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_prior_auth_procedures_request_id"),
        table_name="prior_auth_procedures",
        schema=SCHEMA,
    )
    op.drop_table("prior_auth_procedures", schema=SCHEMA)
    op.drop_index(op.f("ix_audit_events_request_id"), table_name="audit_events", schema=SCHEMA)
    op.drop_table("audit_events", schema=SCHEMA)
    op.drop_table("reviewer_member_conflicts", schema=SCHEMA)
    op.drop_index("ix_pa_queue", table_name="prior_auth_requests", schema=SCHEMA)
    op.drop_table("prior_auth_requests", schema=SCHEMA)
    op.drop_index(
        op.f("ix_intake_rejections_correlation_id"),
        table_name="intake_rejections",
        schema=SCHEMA,
    )
    op.drop_table("intake_rejections", schema=SCHEMA)
    op.drop_table("users", schema=SCHEMA)
    op.drop_table("patient_practice_links", schema=SCHEMA)
    op.drop_index(op.f("ix_coverages_member_id"), table_name="coverages", schema=SCHEMA)
    op.drop_table("coverages", schema=SCHEMA)
    op.drop_table("practices", schema=SCHEMA)
    op.drop_table("members", schema=SCHEMA)
    op.execute("DROP TYPE IF EXISTS procedure_decision")
    op.execute("DROP TYPE IF EXISTS request_status")
    op.execute("DROP TYPE IF EXISTS user_role")
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA}")
