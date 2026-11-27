from __future__ import annotations

import logging
import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.clock import utc_now
from app.identity.schemas import UserContext
from app.prior_auth.models import PriorAuthRequest, RequestStatus
from app.prior_auth.services.common import audit_commit_refresh, get_request, has_coi
from app.shared.errors import ConflictError, ForbiddenError
from app.telemetry import record_claim_conflict

_log = logging.getLogger(__name__)


def claim_request(db: Session, reviewer: UserContext, request_id: uuid.UUID) -> PriorAuthRequest:
    existing = get_request(db, request_id)
    if has_coi(db, reviewer.user_id, existing.member_id):
        raise ForbiddenError("Conflict of interest with this member")

    now = utc_now()
    unclaimed = PriorAuthRequest.claimed_by_user_id.is_(None)
    stmt = (
        update(PriorAuthRequest)
        .where(
            PriorAuthRequest.uuid == request_id,
            PriorAuthRequest.status == RequestStatus.submitted,
            unclaimed,
        )
        .values(
            status=RequestStatus.in_review,
            claimed_by_user_id=reviewer.user_id,
            claimed_at=now,
        )
        .returning(PriorAuthRequest.uuid)
    )
    claimed_id = db.execute(stmt).scalar_one_or_none()
    request_id_str = str(request_id)
    reviewer_id_str = str(reviewer.user_id)
    if claimed_id is None:
        record_claim_conflict()
        _log.warning(
            "claim conflict request_id=%s reviewer_id=%s",
            request_id_str,
            reviewer_id_str,
        )
        raise ConflictError("Request already claimed or not in submitted state")

    request = get_request(db, request_id, load_procedures=True)
    _log.info(
        "prior auth claimed request_id=%s reviewer_id=%s",
        request_id_str,
        reviewer_id_str,
    )
    return audit_commit_refresh(
        db,
        request,
        actor_user_id=reviewer.user_id,
        action="claim",
        payload={"request_id": request_id_str, "reviewer_id": reviewer_id_str},
    )
