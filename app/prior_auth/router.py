from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.identity.models import UserRole
from app.prior_auth.models import PriorAuthRequest, RequestStatus
from app.prior_auth.schemas import (
    DecideIn,
    MemberPriorAuthOut,
    PriorAuthOut,
    ReassignIn,
    SubmitPriorAuthIn,
)
from app.prior_auth.serializers import to_member_out, to_prior_auth_out
from app.prior_auth.services.claim import claim_request
from app.prior_auth.services.decide import decide_request
from app.prior_auth.services.reassign import reassign_request
from app.prior_auth.services.submit import submit_prior_auth
from app.shared.deps import (
    AdminUser,
    CurrentUser,
    DbSession,
    MemberUser,
    OfficeOrAdmin,
    OfficeUser,
    ReviewerUser,
)
from app.shared.errors import ForbiddenError, NotFoundError

router = APIRouter(tags=["prior-auth"])


def _load(db, request_id: uuid.UUID) -> PriorAuthRequest | None:
    return db.scalar(
        select(PriorAuthRequest)
        .where(PriorAuthRequest.id == request_id)
        .options(selectinload(PriorAuthRequest.procedures))
    )


@router.post("/v1/prior-auths", response_model=PriorAuthOut, status_code=201)
def create_prior_auth(body: SubmitPriorAuthIn, db: DbSession, ctx: OfficeUser) -> PriorAuthOut:
    return to_prior_auth_out(submit_prior_auth(db, ctx, body))


@router.get("/v1/prior-auths", response_model=list[PriorAuthOut])
def list_prior_auths(db: DbSession, ctx: OfficeOrAdmin) -> list[PriorAuthOut]:
    q = select(PriorAuthRequest).options(selectinload(PriorAuthRequest.procedures))
    if ctx.role == UserRole.provider_office:
        q = q.where(PriorAuthRequest.practice_id == ctx.practice_id)
    rows = db.scalars(q.order_by(PriorAuthRequest.created_at.desc())).all()
    return [to_prior_auth_out(r) for r in rows]


@router.get("/v1/prior-auths/{request_id}", response_model=PriorAuthOut)
def get_prior_auth(request_id: uuid.UUID, db: DbSession, ctx: CurrentUser) -> PriorAuthOut:
    request = _load(db, request_id)
    if request is None:
        raise NotFoundError("Prior auth request not found")
    if ctx.role == UserRole.provider_office:
        if request.practice_id != ctx.practice_id:
            raise NotFoundError("Prior auth request not found")
    elif ctx.role == UserRole.reviewer:
        own = request.claimed_by_user_id == ctx.user_id
        queueable = (
            request.status == RequestStatus.submitted and request.claimed_by_user_id is None
        )
        if not (own or queueable):
            raise ForbiddenError("Not allowed to view this request")
    elif ctx.role == UserRole.ops_admin:
        pass
    else:
        raise ForbiddenError("Not allowed")
    return to_prior_auth_out(request)


@router.get("/v1/review-queue", response_model=list[PriorAuthOut])
def review_queue(db: DbSession, ctx: ReviewerUser) -> list[PriorAuthOut]:
    rows = db.scalars(
        select(PriorAuthRequest)
        .where(
            PriorAuthRequest.status == RequestStatus.submitted,
            PriorAuthRequest.claimed_by_user_id.is_(None),
        )
        .options(selectinload(PriorAuthRequest.procedures))
        .order_by(PriorAuthRequest.created_at.asc())
    ).all()
    return [to_prior_auth_out(r) for r in rows]


@router.post("/v1/prior-auths/{request_id}/claim", response_model=PriorAuthOut)
def claim(request_id: uuid.UUID, db: DbSession, ctx: ReviewerUser) -> PriorAuthOut:
    return to_prior_auth_out(claim_request(db, ctx, request_id))


@router.post("/v1/prior-auths/{request_id}/decision", response_model=PriorAuthOut)
def decide(request_id: uuid.UUID, body: DecideIn, db: DbSession, ctx: ReviewerUser) -> PriorAuthOut:
    return to_prior_auth_out(decide_request(db, ctx, request_id, body))


@router.post("/v1/prior-auths/{request_id}/reassign", response_model=PriorAuthOut)
def reassign(
    request_id: uuid.UUID, body: ReassignIn, db: DbSession, ctx: AdminUser
) -> PriorAuthOut:
    return to_prior_auth_out(reassign_request(db, ctx, request_id, body.reviewer_id))


@router.get("/v1/me/prior-auths", response_model=list[MemberPriorAuthOut])
def my_prior_auths(db: DbSession, ctx: MemberUser) -> list[MemberPriorAuthOut]:
    rows = db.scalars(
        select(PriorAuthRequest)
        .where(PriorAuthRequest.member_id == ctx.member_id)
        .options(selectinload(PriorAuthRequest.procedures))
        .order_by(PriorAuthRequest.created_at.desc())
    ).all()
    return [to_member_out(r) for r in rows]


@router.get("/v1/me/prior-auths/{request_id}", response_model=MemberPriorAuthOut)
def my_prior_auth(request_id: uuid.UUID, db: DbSession, ctx: MemberUser) -> MemberPriorAuthOut:
    request = _load(db, request_id)
    if request is None or request.member_id != ctx.member_id:
        raise NotFoundError("Prior auth request not found")
    return to_member_out(request)
