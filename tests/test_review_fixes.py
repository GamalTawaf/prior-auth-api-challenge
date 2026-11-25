"""Regression tests for final-review Important findings."""

from __future__ import annotations

import threading
import uuid
from datetime import timedelta

from app.clock import get_today
from app.identity.models import User, UserRole
from app.identity.schemas import UserContext
from app.master_data.models import Coverage, Member, PatientPracticeLink, Practice
from app.prior_auth.models import PriorAuthProcedure, PriorAuthRequest, RequestStatus
from app.prior_auth.schemas import DecideIn, ProcedureDecisionIn
from app.prior_auth.services.decide import decide_request
from app.shared.errors import ConflictError
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from tests.conftest import auth, valid_submit_body


def test_duplicate_procedure_outcomes_rejected(client: TestClient):
    created = client.post(
        "/v1/prior-auths",
        headers=auth(client.seed["tokens"]["office"]),
        json=valid_submit_body(client.seed),
    )
    rid = created.json()["id"]
    client.post(f"/v1/prior-auths/{rid}/claim", headers=auth(client.seed["tokens"]["reviewer"]))
    detail = client.get(f"/v1/prior-auths/{rid}", headers=auth(client.seed["tokens"]["reviewer"]))
    pid = detail.json()["procedures"][0]["id"]
    response = client.post(
        f"/v1/prior-auths/{rid}/decision",
        headers=auth(client.seed["tokens"]["reviewer"]),
        json={
            "outcomes": [
                {"procedure_id": pid, "decision": "approved"},
                {"procedure_id": pid, "decision": "denied", "denial_reason": "x"},
            ]
        },
    )
    assert response.status_code == 422
    assert any(e["error_code"] == "procedures_incomplete" for e in response.json()["errors"])


def test_reassign_rejects_coi_reviewer(client: TestClient):
    created = client.post(
        "/v1/prior-auths",
        headers=auth(client.seed["tokens"]["office"]),
        json=valid_submit_body(client.seed),
    )
    rid = created.json()["id"]
    client.post(f"/v1/prior-auths/{rid}/claim", headers=auth(client.seed["tokens"]["reviewer"]))
    response = client.post(
        f"/v1/prior-auths/{rid}/reassign",
        headers=auth(client.seed["tokens"]["admin"]),
        json={"reviewer_id": str(client.seed["reviewer_coi"].id)},
    )
    assert response.status_code == 422
    assert any(e["error_code"] == "reviewer_coi" for e in response.json()["errors"])


def test_pydantic_units_zero_persists_intake_rejection(client: TestClient):
    body = valid_submit_body(client.seed, procedures=[{"code": "99213", "units": 0}])
    response = client.post(
        "/v1/prior-auths",
        headers=auth(client.seed["tokens"]["office"]),
        json=body,
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload.get("correlation_id")
    assert any(e["error_code"] == "units_too_low" for e in payload["errors"])
    support = client.get(
        f"/v1/support/intake-rejections/{payload['correlation_id']}",
        headers=auth(client.seed["tokens"]["office"]),
    )
    assert support.status_code == 200


def test_auth_uses_db_role_not_token_role(client: TestClient, db):
    import jwt
    from app.config import settings

    # Craft token claiming ops_admin for an office user
    forged = jwt.encode(
        {
            "sub": str(client.seed["office"].id),
            "role": "ops_admin",
            "exp": 9999999999,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    # Should still be treated as office (DB role), not admin
    response = client.get("/v1/prior-auths", headers=auth(forged))
    assert response.status_code == 200
    # Admin-only audit should fail
    created = client.post(
        "/v1/prior-auths",
        headers=auth(client.seed["tokens"]["office"]),
        json=valid_submit_body(client.seed),
    )
    rid = created.json()["id"]
    audit = client.get(f"/v1/prior-auths/{rid}/audit", headers=auth(forged))
    assert audit.status_code == 403


def test_concurrent_decide_exactly_one_wins(engine):
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionLocal() as db:
        practice = Practice(id=uuid.uuid4(), name="Lock Practice")
        member = Member(id=uuid.uuid4(), external_id=f"L-{uuid.uuid4().hex[:6]}", full_name="L")
        db.add_all([practice, member])
        db.flush()
        db.add(PatientPracticeLink(member_id=member.id, practice_id=practice.id))
        today = get_today()
        db.add(
            Coverage(
                member_id=member.id,
                payer_name="P",
                effective_from=today - timedelta(days=1),
                effective_to=today + timedelta(days=30),
            )
        )
        office = User(
            id=uuid.uuid4(),
            email=f"lo-{uuid.uuid4().hex[:6]}@ex.com",
            role=UserRole.provider_office,
            practice_id=practice.id,
            display_name="O",
        )
        reviewer = User(
            id=uuid.uuid4(),
            email=f"lr-{uuid.uuid4().hex[:6]}@ex.com",
            role=UserRole.reviewer,
            display_name="R",
        )
        db.add_all([office, reviewer])
        db.flush()
        request = PriorAuthRequest(
            id=uuid.uuid4(),
            member_id=member.id,
            practice_id=practice.id,
            submitted_by_user_id=office.id,
            diagnosis_icd10="J06.9",
            date_of_service=today,
            status=RequestStatus.in_review,
            claimed_by_user_id=reviewer.id,
        )
        proc = PriorAuthProcedure(code="99213", units=1, sequence=1)
        request.procedures.append(proc)
        db.add(request)
        db.commit()
        request_id = request.id
        proc_id = proc.id
        reviewer_id = reviewer.id

    outcomes: list[str] = []
    barrier = threading.Barrier(2)
    lock = threading.Lock()

    def attempt() -> None:
        with SessionLocal() as session:
            ctx = UserContext(user_id=reviewer_id, role=UserRole.reviewer)
            body = DecideIn(
                outcomes=[ProcedureDecisionIn(procedure_id=proc_id, decision="approved")]
            )
            barrier.wait(timeout=5)
            try:
                decide_request(session, ctx, request_id, body)
                with lock:
                    outcomes.append("won")
            except ConflictError:
                with lock:
                    outcomes.append("lost")

    threads = [threading.Thread(target=attempt), threading.Thread(target=attempt)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)
    assert sorted(outcomes) == ["lost", "won"], outcomes
