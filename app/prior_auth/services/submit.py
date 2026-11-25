from __future__ import annotations

import re
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.writer import write_audit
from app.clock import get_today
from app.identity.schemas import UserContext
from app.intake.models import IntakeRejection
from app.master_data.models import Coverage, PatientPracticeLink
from app.prior_auth.models import PriorAuthProcedure, PriorAuthRequest, RequestStatus
from app.prior_auth.schemas import SubmitPriorAuthIn
from app.shared.errors import FieldError, ValidationFailure
from app.telemetry import record_intake_rejection

ICD10_RE = re.compile(r"^[A-Z][0-9][0-9A-Z](?:\.[0-9A-Z]{1,4})?$", re.IGNORECASE)
CPT_RE = re.compile(r"^[A-Z0-9]{5}$", re.IGNORECASE)


def submit_prior_auth(db: Session, ctx: UserContext, body: SubmitPriorAuthIn) -> PriorAuthRequest:
    if ctx.practice_id is None:
        correlation_id = uuid.uuid4().hex
        raise ValidationFailure(
            correlation_id=correlation_id,
            errors=[
                FieldError(
                    error_code="missing_practice",
                    field="actor",
                    message="Office user must belong to a practice",
                )
            ],
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
        correlation_id = uuid.uuid4().hex
        field_errors = [e.model_dump() for e in errors]
        rejection = IntakeRejection(
            correlation_id=correlation_id,
            actor_user_id=ctx.user_id,
            practice_id=ctx.practice_id,
            payload_snapshot=payload,
            field_errors=field_errors,
        )
        db.add(rejection)
        db.flush()
        practice_id_str = str(ctx.practice_id)
        write_audit(
            db,
            actor_user_id=ctx.user_id,
            action="intake_reject",
            payload={
                "correlation_id": correlation_id,
                "fields": [e.field for e in errors],
                "practice_id": practice_id_str,
            },
            intake_rejection_id=rejection.id,
        )
        db.commit()
        record_intake_rejection()
        raise ValidationFailure(correlation_id=correlation_id, errors=errors)

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
    request_id_str = str(request.id)
    member_id_str = str(body.member_id)
    write_audit(
        db,
        actor_user_id=ctx.user_id,
        action="submit",
        payload={
            "request_id": request_id_str,
            "member_id": member_id_str,
            "procedure_codes": [p.code for p in request.procedures],
        },
        request_id=request.id,
    )
    db.commit()
    db.refresh(request)
    return request
