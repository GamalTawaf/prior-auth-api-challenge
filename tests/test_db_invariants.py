import uuid

import pytest
from app.clock import get_today
from app.prior_auth.models import PriorAuthRequest, RequestStatus
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.conftest import auth, valid_submit_body


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
    created = client.post(
        "/v1/prior-auths",
        headers=auth(client.seed["tokens"]["office"]),
        json=valid_submit_body(client.seed),
    )
    rid = created.json()["id"]
    client.post(f"/v1/prior-auths/{rid}/claim", headers=auth(client.seed["tokens"]["reviewer"]))
    procs = created.json()["procedures"]
    # refresh procedures after claim via get
    detail = client.get(f"/v1/prior-auths/{rid}", headers=auth(client.seed["tokens"]["reviewer"]))
    procs = detail.json()["procedures"]
    decided = client.post(
        f"/v1/prior-auths/{rid}/decision",
        headers=auth(client.seed["tokens"]["reviewer"]),
        json={"outcomes": [{"procedure_id": p["id"], "decision": "approved"} for p in procs]},
    )
    assert decided.status_code == 200
    row = db.execute(
        text("SELECT decided_by_user_id IS NOT NULL FROM prior_auth_requests WHERE id = :id"),
        {"id": rid},
    ).scalar()
    assert row is True
