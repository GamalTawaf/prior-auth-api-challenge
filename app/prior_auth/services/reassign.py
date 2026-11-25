from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.writer import write_audit
from app.identity.models import User, UserRole
from app.identity.schemas import UserContext
from app.master_data.models import ReviewerMemberConflict
from app.prior_auth.models import PriorAuthRequest, RequestStatus
from app.shared.errors import ConflictError, FieldError, NotFoundError, ValidationFailure


def reassign_request(
    db: Session, admin: UserContext, request_id: uuid.UUID, reviewer_id: uuid.UUID
) -> PriorAuthRequest:
    stmt = select(PriorAuthRequest).where(PriorAuthRequest.id == request_id).with_for_update()
    request = db.scalar(stmt)
    if request is None:
        raise NotFoundError("Prior auth request not found")
    if request.status == RequestStatus.decided:
        raise ConflictError("Cannot reassign a decided request")
    if request.status != RequestStatus.in_review:
        raise ConflictError("Request must be in_review to reassign")

    reviewer = db.get(User, reviewer_id)
    if reviewer is None or reviewer.role != UserRole.reviewer:
        correlation_id = uuid.uuid4().hex
        raise ValidationFailure(
            correlation_id=correlation_id,
            errors=[
                FieldError(
                    error_code="invalid_reviewer",
                    field="reviewer_id",
                    message="reviewer_id must reference a reviewer user",
                )
            ],
        )
    coi_stmt = select(ReviewerMemberConflict).where(
        ReviewerMemberConflict.reviewer_user_id == reviewer_id,
        ReviewerMemberConflict.member_id == request.member_id,
    )
    coi = db.scalar(coi_stmt)
    if coi is not None:
        correlation_id = uuid.uuid4().hex
        raise ValidationFailure(
            correlation_id=correlation_id,
            errors=[
                FieldError(
                    error_code="reviewer_coi",
                    field="reviewer_id",
                    message="Reviewer has a conflict of interest with this member",
                )
            ],
        )

    previous = request.claimed_by_user_id
    request.claimed_by_user_id = reviewer_id
    request.claimed_at = datetime.now(UTC)
    previous_str = str(previous) if previous else None
    reviewer_id_str = str(reviewer_id)
    request_id_str = str(request_id)
    write_audit(
        db,
        actor_user_id=admin.user_id,
        action="reassign",
        payload={"request_id": request_id_str, "from": previous_str, "to": reviewer_id_str},
        request_id=request_id,
    )
    db.commit()
    db.refresh(request)
    return request
