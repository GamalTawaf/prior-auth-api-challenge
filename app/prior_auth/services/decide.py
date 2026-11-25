from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.audit.writer import write_audit
from app.identity.schemas import UserContext
from app.master_data.models import ReviewerMemberConflict
from app.prior_auth.models import PriorAuthRequest, ProcedureDecision, RequestStatus
from app.prior_auth.schemas import DecideIn
from app.shared.errors import (
    ConflictError,
    FieldError,
    ForbiddenError,
    NotFoundError,
    ValidationFailure,
)


def decide_request(
    db: Session, reviewer: UserContext, request_id: uuid.UUID, body: DecideIn
) -> PriorAuthRequest:
    procedures_load = selectinload(PriorAuthRequest.procedures)
    stmt = (
        select(PriorAuthRequest)
        .where(PriorAuthRequest.id == request_id)
        .options(procedures_load)
        .with_for_update()
    )
    request = db.scalar(stmt)
    if request is None:
        raise NotFoundError("Prior auth request not found")
    if request.status == RequestStatus.decided:
        raise ConflictError("Request already decided")
    if request.status != RequestStatus.in_review or request.claimed_by_user_id != reviewer.user_id:
        raise ForbiddenError("Only the claim holder may decide")

    coi_stmt = select(ReviewerMemberConflict).where(
        ReviewerMemberConflict.reviewer_user_id == reviewer.user_id,
        ReviewerMemberConflict.member_id == request.member_id,
    )
    coi = db.scalar(coi_stmt)
    if coi is not None:
        raise ForbiddenError("Conflict of interest with this member")

    by_id = {p.id: p for p in request.procedures}
    outcome_ids = [o.procedure_id for o in body.outcomes]
    errors: list[FieldError] = []
    if len(outcome_ids) != len(by_id) or set(outcome_ids) != set(by_id):
        errors.append(
            FieldError(
                error_code="procedures_incomplete",
                field="outcomes",
                message="Decision must cover every procedure exactly once",
            )
        )

    for outcome in body.outcomes:
        if outcome.decision not in ("approved", "denied"):
            errors.append(
                FieldError(
                    error_code="invalid_decision",
                    field=f"outcomes[{outcome.procedure_id}].decision",
                    message="Decision must be approved or denied",
                )
            )
        denial_blank = not (outcome.denial_reason or "").strip()
        if outcome.decision == "denied" and denial_blank:
            errors.append(
                FieldError(
                    error_code="denial_reason_required",
                    field=f"outcomes[{outcome.procedure_id}].denial_reason",
                    message="Denial reason is required when denying",
                )
            )

    if errors:
        correlation_id = uuid.uuid4().hex
        raise ValidationFailure(correlation_id=correlation_id, errors=errors)

    now = datetime.now(UTC)
    for outcome in body.outcomes:
        proc = by_id[outcome.procedure_id]
        proc.decision = ProcedureDecision(outcome.decision)
        if outcome.decision == "denied":
            proc.denial_reason = outcome.denial_reason.strip() if outcome.denial_reason else None
        else:
            proc.denial_reason = None

    request.status = RequestStatus.decided
    request.decided_by_user_id = reviewer.user_id
    request.decided_at = now
    request_id_str = str(request_id)
    outcomes_payload = [
        {
            "procedure_id": str(o.procedure_id),
            "decision": o.decision,
            "denial_reason": o.denial_reason,
        }
        for o in body.outcomes
    ]
    write_audit(
        db,
        actor_user_id=reviewer.user_id,
        action="decide",
        payload={"request_id": request_id_str, "outcomes": outcomes_payload},
        request_id=request_id,
    )
    db.commit()
    db.refresh(request)
    return request
