import uuid

import pytest
from app.clock import get_today
from app.prior_auth.models import PriorAuthRequest, RequestStatus
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.conftest import approve_all_outcomes, decide_as, get_as, submit_and_claim


def test_decided_requires_actor_check(db: Session, seed_data: dict):
    request = PriorAuthRequest(
        id=uuid.uuid4(),
        member_id=seed_data["member"].id,
        practice_id=seed_data["practice"].id,
        submitted_by_user_id=seed_data["office"].id,
        diagnosis_icd10="J06.9",
        date_of_service=get_today(),
        status=RequestStatus.decided,
        decided_by_user_id=None,
    )
    db.add(request)
    with pytest.raises(IntegrityError):
        db.flush()


def test_http_decide_always_sets_decided_by(client: TestClient, db: Session):
    data = submit_and_claim(client)
    rid = data["id"]
    detail = get_as(client, rid, "reviewer")
    procs = detail.json()["procedures"]
    decided = decide_as(client, rid, approve_all_outcomes(procs))
    assert decided.status_code == 200
    row = db.execute(
        text("SELECT decided_by_user_id IS NOT NULL FROM prior_auth_requests WHERE id = :id"),
        {"id": rid},
    ).scalar()
    assert row is True
