from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ProcedureIn(BaseModel):
    code: str = Field(min_length=5, max_length=10)
    units: int = Field(ge=1)


class SubmitPriorAuthIn(BaseModel):
    member_id: uuid.UUID
    diagnosis_icd10: str
    date_of_service: date
    clinical_note: str | None = None
    procedures: list[ProcedureIn] = Field(min_length=1)


class ProcedureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    units: int
    sequence: int
    decision: str
    denial_reason: str | None = None


class PriorAuthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    member_id: uuid.UUID
    practice_id: uuid.UUID
    submitted_by_user_id: uuid.UUID
    diagnosis_icd10: str
    date_of_service: date
    clinical_note: str | None
    status: str
    claimed_by_user_id: uuid.UUID | None
    claimed_at: datetime | None
    decided_by_user_id: uuid.UUID | None
    decided_at: datetime | None
    created_at: datetime
    procedures: list[ProcedureOut]


class MemberProcedureStatus(StrEnum):
    approved = "approved"
    not_approved = "not_approved"
    pending = "pending"


class MemberProcedureOut(BaseModel):
    id: uuid.UUID
    code: str
    units: int
    sequence: int
    status: MemberProcedureStatus


class MemberPriorAuthOut(BaseModel):
    id: uuid.UUID
    member_id: uuid.UUID
    practice_id: uuid.UUID
    diagnosis_icd10: str
    date_of_service: date
    status: str
    decided_at: datetime | None
    created_at: datetime
    procedures: list[MemberProcedureOut]


class ProcedureDecisionIn(BaseModel):
    procedure_id: uuid.UUID
    decision: str
    denial_reason: str | None = None


class DecideIn(BaseModel):
    outcomes: list[ProcedureDecisionIn] = Field(min_length=1)


class ReassignIn(BaseModel):
    reviewer_id: uuid.UUID
