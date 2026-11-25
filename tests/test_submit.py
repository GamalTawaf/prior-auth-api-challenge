from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditEvent
from app.clock import get_today
from app.prior_auth.models import PriorAuthRequest, RequestStatus
from tests.conftest import auth, valid_submit_body


def test_submit_happy_path(client: TestClient, db: Session):
    body = valid_submit_body(client.seed)
    response = client.post(
        "/v1/prior-auths",
        headers=auth(client.seed["tokens"]["office"]),
        json=body,
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "submitted"
    assert data["clinical_note"] == "Patient needs procedure"
    assert len(data["procedures"]) == 1

    request = db.get(PriorAuthRequest, data["id"])
    assert request is not None
    assert request.status == RequestStatus.submitted
    audit = db.scalars(
        select(AuditEvent).where(AuditEvent.request_id == request.id, AuditEvent.action == "submit")
    ).first()
    assert audit is not None


def test_unlinked_patient_422_with_correlation(client: TestClient):
    body = valid_submit_body(client.seed, member_id=str(client.seed["unlinked"].id))
    response = client.post(
        "/v1/prior-auths",
        headers=auth(client.seed["tokens"]["office"]),
        json=body,
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["correlation_id"]
    assert any(e["error_code"] == "member_not_linked" for e in payload["errors"])


def test_past_dos(client: TestClient):
    body = valid_submit_body(
        client.seed, date_of_service=(get_today() - timedelta(days=1)).isoformat()
    )
    response = client.post(
        "/v1/prior-auths",
        headers=auth(client.seed["tokens"]["office"]),
        json=body,
    )
    assert response.status_code == 422
    assert any(e["error_code"] == "dos_in_past" for e in response.json()["errors"])


def test_dos_too_far(client: TestClient):
    body = valid_submit_body(
        client.seed, date_of_service=(get_today() + timedelta(days=366)).isoformat()
    )
    response = client.post(
        "/v1/prior-auths",
        headers=auth(client.seed["tokens"]["office"]),
        json=body,
    )
    assert response.status_code == 422
    assert any(e["error_code"] == "dos_too_far" for e in response.json()["errors"])


def test_no_coverage(client: TestClient, db: Session):
    # expire coverage
    from app.master_data.models import Coverage

    cov = db.scalars(
        select(Coverage).where(Coverage.member_id == client.seed["member"].id)
    ).one()
    cov.effective_to = get_today() - timedelta(days=1)
    db.flush()
    body = valid_submit_body(client.seed)
    response = client.post(
        "/v1/prior-auths",
        headers=auth(client.seed["tokens"]["office"]),
        json=body,
    )
    assert response.status_code == 422
    assert any(e["error_code"] == "no_coverage" for e in response.json()["errors"])


def test_units_31_hard_reject(client: TestClient):
    body = valid_submit_body(client.seed, procedures=[{"code": "99213", "units": 31}])
    response = client.post(
        "/v1/prior-auths",
        headers=auth(client.seed["tokens"]["office"]),
        json=body,
    )
    assert response.status_code == 422
    assert any(e["error_code"] == "units_likely_typo" for e in response.json()["errors"])
    assert "typo" in response.json()["errors"][0]["message"].lower() or any(
        "typo" in e["message"].lower() for e in response.json()["errors"]
    )


def test_office_list_and_get_practice_scoped(client: TestClient):
    created = client.post(
        "/v1/prior-auths",
        headers=auth(client.seed["tokens"]["office"]),
        json=valid_submit_body(client.seed),
    )
    assert created.status_code == 201
    rid = created.json()["id"]
    listed = client.get("/v1/prior-auths", headers=auth(client.seed["tokens"]["office"]))
    assert listed.status_code == 200
    assert any(r["id"] == rid for r in listed.json())
    got = client.get(f"/v1/prior-auths/{rid}", headers=auth(client.seed["tokens"]["office"]))
    assert got.status_code == 200
    assert got.json()["id"] == rid
