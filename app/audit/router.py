from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.audit.models import AuditEvent
from app.audit.schemas import AuditEventOut
from app.prior_auth.models import PriorAuthRequest
from app.shared.deps import AdminUser, DbSession
from app.shared.errors import NotFoundError

router = APIRouter(tags=["audit"])


@router.get("/v1/prior-auths/{request_id}/audit", response_model=list[AuditEventOut])
def get_audit(request_id: uuid.UUID, db: DbSession, ctx: AdminUser) -> list[AuditEventOut]:
    if db.get(PriorAuthRequest, request_id) is None:
        raise NotFoundError("Prior auth request not found")
    oldest_first = AuditEvent.at.asc()
    stmt = select(AuditEvent).where(AuditEvent.request_id == request_id).order_by(oldest_first)
    rows = db.scalars(stmt).all()
    return [AuditEventOut.model_validate(r) for r in rows]
