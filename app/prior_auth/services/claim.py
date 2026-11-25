from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.audit.writer import write_audit
from app.identity.schemas import UserContext
from app.master_data.models import ReviewerMemberConflict
from app.prior_auth.models import PriorAuthRequest, RequestStatus
from app.shared.errors import ConflictError, ForbiddenError, NotFoundError
from app.telemetry import record_claim_conflict


def _has_coi(db: Session, reviewer_id: uuid.UUID, member_id: uuid.UUID) -> bool:
    stmt = select(ReviewerMemberConflict).where(
        ReviewerMemberConflict.reviewer_user_id == reviewer_id,
        ReviewerMemberConflict.member_id == member_id,
    )
    row = db.scalar(stmt)
    return row is not None


def claim_request(db: Session, reviewer: UserContext, request_id: uuid.UUID) -> PriorAuthRequest:
    existing = db.get(PriorAuthRequest, request_id)
    if existing is None:
        raise NotFoundError("Prior auth request not found")
    if _has_coi(db, reviewer.user_id, existing.member_id):
        raise ForbiddenError("Conflict of interest with this member")

    now = datetime.now(UTC)
    unclaimed = PriorAuthRequest.claimed_by_user_id.is_(None)
    stmt = (
        update(PriorAuthRequest)
        .where(
            PriorAuthRequest.id == request_id,
            PriorAuthRequest.status == RequestStatus.submitted,
            unclaimed,
        )
        .values(
            status=RequestStatus.in_review,
            claimed_by_user_id=reviewer.user_id,
            claimed_at=now,
        )
        .returning(PriorAuthRequest.id)
    )
    result = db.execute(stmt)
    row = result.first()
    if row is None:
        record_claim_conflict()
        raise ConflictError("Request already claimed or not in submitted state")

    request = db.get(PriorAuthRequest, request_id)
    assert request is not None
    request_id_str = str(request_id)
    reviewer_id_str = str(reviewer.user_id)
    write_audit(
        db,
        actor_user_id=reviewer.user_id,
        action="claim",
        payload={"request_id": request_id_str, "reviewer_id": reviewer_id_str},
        request_id=request_id,
    )
    db.commit()
    db.refresh(request)
    return request
