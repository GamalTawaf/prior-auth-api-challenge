from __future__ import annotations

from fastapi import APIRouter

from app.intake.schemas import IntakeRejectionOut
from app.intake.services import get_intake_rejection
from app.shared.deps import DbSession, OfficeOrAdmin

router = APIRouter(tags=["support"])


@router.get(
    "/v1/support/intake-rejections/{correlation_id}",
    response_model=IntakeRejectionOut,
)
def lookup_intake_rejection(
    correlation_id: str, db: DbSession, ctx: OfficeOrAdmin
) -> IntakeRejectionOut:
    return IntakeRejectionOut.model_validate(get_intake_rejection(db, ctx, correlation_id))
