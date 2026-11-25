from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.audit.writer import write_audit
from app.identity.models import User, UserRole
from app.identity.schemas import UserContext
from app.prior_auth.models import PriorAuthRequest, RequestStatus
from app.shared.errors import ConflictError, FieldError, NotFoundError, ValidationFailure


def reassign_request(
    db: Session, admin: UserContext, request_id: uuid.UUID, reviewer_id: uuid.UUID
) -> PriorAuthRequest:
    request = db.get(PriorAuthRequest, request_id)
    if request is None:
        raise NotFoundError("Prior auth request not found")
    if request.status == RequestStatus.decided:
        raise ConflictError("Cannot reassign a decided request")
    if request.status != RequestStatus.in_review:
        raise ConflictError("Request must be in_review to reassign")

    reviewer = db.get(User, reviewer_id)
    if reviewer is None or reviewer.role != UserRole.reviewer:
        raise ValidationFailure(
            correlation_id=str(uuid.uuid4()),
            errors=[
                FieldError(
                    error_code="invalid_reviewer",
                    field="reviewer_id",
                    message="reviewer_id must reference a reviewer user",
                )
            ],
        )

    previous = request.claimed_by_user_id
    request.claimed_by_user_id = reviewer_id
    request.claimed_at = datetime.now(UTC)
    write_audit(
        db,
        actor_user_id=admin.user_id,
        action="reassign",
        payload={
            "request_id": str(request_id),
            "from": str(previous) if previous else None,
            "to": str(reviewer_id),
        },
        request_id=request_id,
    )
    db.commit()
    db.refresh(request)
    return request
