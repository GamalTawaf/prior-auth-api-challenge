from __future__ import annotations

import logging
import re
import uuid
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.audit.service import write_audit
from app.clock import get_today, utc_now
from app.identity.models import User, UserRole
from app.identity.schemas import UserContext
from app.intake.service import persist_intake_rejection
from app.master_data.models import Coverage, PatientPracticeLink
from app.outbox.service import enqueue_decision_notice
from app.prior_auth.helpers import (
    audit_commit_refresh,
    get_request,
    get_request_for_update,
    has_coi,
)
from app.prior_auth.idempotency import store_record
from app.prior_auth.models import (
    PriorAuthProcedure,
    PriorAuthRequest,
    ProcedureDecision,
    RequestStatus,
)
from app.prior_auth.schemas import DecideIn, SubmitPriorAuthIn
from app.prior_auth.serializers import to_prior_auth_out
from app.shared.errors import (
    ConflictError,
    FieldError,
    ForbiddenError,
    raise_field,
    raise_validation,
)
from app.telemetry import record_claim_conflict

ICD10_RE = re.compile(r"^[A-Z][0-9][0-9A-Z](?:\.[0-9A-Z]{1,4})?$", re.IGNORECASE)
CPT_RE = re.compile(r"^[A-Z0-9]{5}$", re.IGNORECASE)
_log = logging.getLogger(__name__)


def _commit_refresh(db: Session, request: PriorAuthRequest) -> PriorAuthRequest:
    db.commit()
    db.refresh(request)
    return request


def submit_prior_auth(
    db: Session,
    ctx: UserContext,
    body: SubmitPriorAuthIn,
    *,
    idempotency_key: str | None = None,
    request_hash: str | None = None,
) -> PriorAuthRequest:
    if ctx.practice_id is None:
        raise_field(
            "missing_practice",
            "actor",
            "Office user must belong to a practice",
        )

    errors: list[FieldError] = []
    today = get_today()
    payload = body.model_dump(mode="json")

    link_stmt = select(PatientPracticeLink).where(
        PatientPracticeLink.member_id == body.member_id,
        PatientPracticeLink.practice_id == ctx.practice_id,
    )
    linked = db.scalar(link_stmt)
    if linked is None:
        errors.append(
            FieldError(
                error_code="member_not_linked",
                field="member_id",
                message="Member is not linked to this practice",
            )
        )
        # Do not run member-derived checks (coverage) — avoids cross-tenant probing.
        correlation_id = persist_intake_rejection(
            db,
            actor_user_id=ctx.user_id,
            practice_id=ctx.practice_id,
            payload=payload,
            errors=errors,
        )
        raise_validation(errors, correlation_id=correlation_id)

    if body.date_of_service < today:
        errors.append(
            FieldError(
                error_code="dos_in_past",
                field="date_of_service",
                message="Date of service must be today or later",
            )
        )
    max_dos = today + timedelta(days=365)
    if body.date_of_service > max_dos:
        errors.append(
            FieldError(
                error_code="dos_too_far",
                field="date_of_service",
                message="Date of service must be within 365 days",
            )
        )

    open_ended = Coverage.effective_to.is_(None)
    covers_dos = Coverage.effective_to >= body.date_of_service
    coverage_stmt = select(Coverage).where(
        Coverage.member_id == body.member_id,
        Coverage.effective_from <= body.date_of_service,
        open_ended | covers_dos,
    )
    coverage = db.scalars(coverage_stmt).first()
    if coverage is None:
        errors.append(
            FieldError(
                error_code="no_coverage",
                field="member_id",
                message="No active coverage overlapping date of service",
            )
        )

    diagnosis = body.diagnosis_icd10.strip()
    if not ICD10_RE.match(diagnosis):
        errors.append(
            FieldError(
                error_code="invalid_icd10",
                field="diagnosis_icd10",
                message="ICD-10 format looks invalid",
            )
        )

    if not body.procedures:
        errors.append(
            FieldError(
                error_code="procedures_required",
                field="procedures",
                message="At least one procedure is required",
            )
        )

    for i, proc in enumerate(body.procedures):
        prefix = f"procedures[{i}]"
        code = proc.code.strip()
        if not CPT_RE.match(code):
            errors.append(
                FieldError(
                    error_code="invalid_procedure_code",
                    field=f"{prefix}.code",
                    message="CPT/HCPCS code must be 5 alphanumeric characters",
                )
            )
        if proc.units < 1:
            errors.append(
                FieldError(
                    error_code="units_too_low",
                    field=f"{prefix}.units",
                    message="Units must be at least 1",
                )
            )
        if proc.units > 30:
            errors.append(
                FieldError(
                    error_code="units_likely_typo",
                    field=f"{prefix}.units",
                    message="Units > 30 is almost always a typo; hard reject",
                )
            )

    if errors:
        correlation_id = persist_intake_rejection(
            db,
            actor_user_id=ctx.user_id,
            practice_id=ctx.practice_id,
            payload=payload,
            errors=errors,
        )
        raise_validation(errors, correlation_id=correlation_id)

    diagnosis_norm = diagnosis.upper()
    request = PriorAuthRequest(
        member_id=body.member_id,
        practice_id=ctx.practice_id,
        submitted_by_user_id=ctx.user_id,
        diagnosis_icd10=diagnosis_norm,
        date_of_service=body.date_of_service,
        clinical_note=body.clinical_note,
        status=RequestStatus.submitted,
    )
    for i, proc in enumerate(body.procedures, start=1):
        code_norm = proc.code.strip().upper()
        request.procedures.append(PriorAuthProcedure(code=code_norm, units=proc.units, sequence=i))
    db.add(request)
    db.flush()
    request_id_str = str(request.uuid)
    member_id_str = str(body.member_id)
    procedure_codes = [p.code for p in request.procedures]
    write_audit(
        db,
        actor_user_id=ctx.user_id,
        action="submit",
        payload={
            "request_id": request_id_str,
            "member_id": member_id_str,
            "procedure_codes": procedure_codes,
        },
        request_id=request.uuid,
    )
    practice_id_str = str(ctx.practice_id)
    procedure_count = len(procedure_codes)
    _log.info(
        "prior auth submitted request_id=%s practice_id=%s member_id=%s procedures=%s",
        request_id_str,
        practice_id_str,
        member_id_str,
        procedure_count,
    )
    # Separate guards (not one `and` chain) so `and`→`or` cannot no-op on HTTP.
    # practice_id is already required at the top of this function.
    if idempotency_key is None:
        return _commit_refresh(db, request)
    if request_hash is None:
        return _commit_refresh(db, request)
    db.refresh(request)
    response = to_prior_auth_out(request)
    store_record(
        db,
        practice_id=ctx.practice_id,
        key=idempotency_key,
        request_hash=request_hash,
        request_id=request.uuid,
        response=response,
    )
    return _commit_refresh(db, request)


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


def decide_request(db: Session, reviewer: UserContext, request_id: uuid.UUID, body: DecideIn):
    request = get_request_for_update(db, request_id, load_procedures=True)
    if request.status == RequestStatus.decided:
        raise ConflictError("Request already decided")
    if request.status != RequestStatus.in_review or request.claimed_by_user_id != reviewer.user_id:
        raise ForbiddenError("Only the claim holder may decide")
    if has_coi(db, reviewer.user_id, request.member_id):
        raise ForbiddenError("Conflict of interest with this member")

    by_id = {p.uuid: p for p in request.procedures}
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
        raise_validation(errors)

    now = utc_now()
    for outcome in body.outcomes:
        proc = by_id[outcome.procedure_id]
        proc.decision = ProcedureDecision(outcome.decision)
        if outcome.decision == "denied":
            proc.denial_reason = str(outcome.denial_reason).strip()
        else:
            proc.denial_reason = None

    request.status = RequestStatus.decided
    request.decided_by_user_id = reviewer.user_id
    request.decided_at = now
    outcomes_payload = [
        {
            "procedure_id": str(o.procedure_id),
            "decision": o.decision,
            "denial_reason": o.denial_reason,
        }
        for o in body.outcomes
    ]
    enqueue_decision_notice(db, request)
    request_id_str = str(request_id)
    reviewer_id_str = str(reviewer.user_id)
    approved = sum(1 for o in body.outcomes if o.decision == "approved")
    denied = sum(1 for o in body.outcomes if o.decision == "denied")
    _log.info(
        "prior auth decided request_id=%s reviewer_id=%s approved=%s denied=%s",
        request_id_str,
        reviewer_id_str,
        approved,
        denied,
    )
    return audit_commit_refresh(
        db,
        request,
        actor_user_id=reviewer.user_id,
        action="decide",
        payload={"request_id": request_id_str, "outcomes": outcomes_payload},
    )


def reassign_request(
    db: Session, admin: UserContext, request_id: uuid.UUID, reviewer_id: uuid.UUID
):
    # Status is enforced by the conditional UPDATE below (avoids duplicate early-check strings
    # that mutmut can flip without a covering assertion path).
    # Lock before capturing previous so concurrent reassigns cannot both audit from=A.
    request = get_request_for_update(db, request_id)
    previous = request.claimed_by_user_id

    reviewer = db.get(User, reviewer_id)
    if reviewer is None or reviewer.role != UserRole.reviewer:
        raise_field(
            "invalid_reviewer",
            "reviewer_id",
            "reviewer_id must reference a reviewer user",
        )
    if has_coi(db, reviewer_id, request.member_id):
        raise_field(
            "reviewer_coi",
            "reviewer_id",
            "Reviewer has a conflict of interest with this member",
        )

    now = utc_now()
    stmt = (
        update(PriorAuthRequest)
        .where(
            PriorAuthRequest.uuid == request_id,
            PriorAuthRequest.status == RequestStatus.in_review,
        )
        .values(
            claimed_by_user_id=reviewer_id,
            claimed_at=now,
        )
        .returning(PriorAuthRequest.uuid)
    )
    moved_id = db.execute(stmt).scalar_one_or_none()
    if moved_id is None:
        fresh = get_request(db, request_id)
        if fresh.status == RequestStatus.decided:
            raise ConflictError("Cannot reassign a decided request")
        raise ConflictError("Request must be in_review to reassign")

    request = get_request(db, request_id, load_procedures=True)
    # in_review rows always have a claimant (DB CHECK); previous is never None here.
    previous_str = str(previous)
    request_id_str = str(request_id)
    to_str = str(reviewer_id)
    _log.info(
        "prior auth reassigned request_id=%s from=%s to=%s",
        request_id_str,
        previous_str,
        to_str,
    )
    return audit_commit_refresh(
        db,
        request,
        actor_user_id=admin.user_id,
        action="reassign",
        payload={
            "request_id": request_id_str,
            "from": previous_str,
            "to": to_str,
        },
    )
