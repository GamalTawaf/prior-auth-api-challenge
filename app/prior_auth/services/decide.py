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
    request = db.scalar(
        select(PriorAuthRequest)
        .where(PriorAuthRequest.id == request_id)
        .options(selectinload(PriorAuthRequest.procedures))
    )
    if request is None:
        raise NotFoundError("Prior auth request not found")
    if request.status == RequestStatus.decided:
        raise ConflictError("Request already decided")
    if request.status != RequestStatus.in_review or request.claimed_by_user_id != reviewer.user_id:
        raise ForbiddenError("Only the claim holder may decide")

    coi = db.scalar(
        select(ReviewerMemberConflict).where(
            ReviewerMemberConflict.reviewer_user_id == reviewer.user_id,
            ReviewerMemberConflict.member_id == request.member_id,
        )
    )
    if coi is not None:
        raise ForbiddenError("Conflict of interest with this member")

    by_id = {p.id: p for p in request.procedures}
    outcome_ids = {o.procedure_id for o in body.outcomes}
    errors: list[FieldError] = []
    if outcome_ids != set(by_id):
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
        if outcome.decision == "denied" and not (outcome.denial_reason or "").strip():
            errors.append(
                FieldError(
                    error_code="denial_reason_required",
                    field=f"outcomes[{outcome.procedure_id}].denial_reason",
                    message="Denial reason is required when denying",
                )
            )

    if errors:
        raise ValidationFailure(correlation_id=str(uuid.uuid4()), errors=errors)

    now = datetime.now(UTC)
    for outcome in body.outcomes:
        proc = by_id[outcome.procedure_id]
        proc.decision = ProcedureDecision(outcome.decision)
        proc.denial_reason = (
            outcome.denial_reason.strip() if outcome.decision == "denied" else None
        )

    request.status = RequestStatus.decided
    request.decided_by_user_id = reviewer.user_id
    request.decided_at = now
    write_audit(
        db,
        actor_user_id=reviewer.user_id,
        action="decide",
        payload={
            "request_id": str(request_id),
            "outcomes": [
                {
                    "procedure_id": str(o.procedure_id),
                    "decision": o.decision,
                    "denial_reason": o.denial_reason,
                }
                for o in body.outcomes
            ],
        },
        request_id=request_id,
    )
    db.commit()
    db.refresh(request)
    return request
