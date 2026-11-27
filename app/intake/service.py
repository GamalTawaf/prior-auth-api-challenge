from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import write_audit
from app.identity.models import UserRole
from app.identity.schemas import UserContext
from app.intake.models import IntakeRejection
from app.shared.errors import FieldError, NotFoundError
from app.telemetry import record_intake_rejection

_log = logging.getLogger(__name__)


def persist_intake_rejection(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    practice_id: uuid.UUID,
    payload: dict,
    errors: list[FieldError],
) -> str:
    """Write IntakeRejection + audit; return correlation_id (caller raises ValidationFailure)."""
    correlation_id = uuid.uuid4().hex
    field_errors = [e.model_dump() for e in errors]
    rejection = IntakeRejection(
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        practice_id=practice_id,
        payload_snapshot=payload,
        field_errors=field_errors,
    )
    db.add(rejection)
    db.flush()
    practice_id_str = str(practice_id)
    write_audit(
        db,
        actor_user_id=actor_user_id,
        action="intake_reject",
        payload={
            "correlation_id": correlation_id,
            "fields": [e.field for e in errors],
            "practice_id": practice_id_str,
        },
        intake_rejection_id=rejection.uuid,
    )
    db.commit()
    record_intake_rejection()
    fields = [e.field for e in errors]
    practice_id_log = str(practice_id)
    _log.warning(
        "intake rejected correlation_id=%s practice_id=%s fields=%s",
        correlation_id,
        practice_id_log,
        fields,
    )
    return correlation_id


def get_intake_rejection(db: Session, ctx: UserContext, correlation_id: str) -> IntakeRejection:
    stmt = select(IntakeRejection).where(IntakeRejection.correlation_id == correlation_id)
    row = db.scalar(stmt)
    if row is None:
        raise NotFoundError("Intake rejection not found")
    if ctx.role == UserRole.ops_admin:
        return row
    if ctx.role == UserRole.provider_office and row.practice_id == ctx.practice_id:
        return row
    raise NotFoundError("Intake rejection not found")
