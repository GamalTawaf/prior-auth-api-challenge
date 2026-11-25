from __future__ import annotations

import threading
import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.clock import get_today
from app.identity.models import User, UserRole
from app.identity.schemas import UserContext
from app.master_data.models import Coverage, Member, PatientPracticeLink, Practice
from app.prior_auth.models import PriorAuthProcedure, PriorAuthRequest, RequestStatus
from app.prior_auth.services.claim import claim_request
from app.shared.errors import ConflictError
from tests.conftest import auth, valid_submit_body


def test_claim_via_http(client: TestClient):
    created = client.post(
        "/v1/prior-auths",
        headers=auth(client.seed["tokens"]["office"]),
        json=valid_submit_body(client.seed),
    )
    rid = created.json()["id"]
    queue = client.get("/v1/review-queue", headers=auth(client.seed["tokens"]["reviewer"]))
    assert any(r["id"] == rid for r in queue.json())
    claimed = client.post(
        f"/v1/prior-auths/{rid}/claim",
        headers=auth(client.seed["tokens"]["reviewer"]),
    )
    assert claimed.status_code == 200
    assert claimed.json()["status"] == "in_review"
    assert claimed.json()["claimed_by_user_id"] == str(client.seed["reviewer"].id)

    lost = client.post(
        f"/v1/prior-auths/{rid}/claim",
        headers=auth(client.seed["tokens"]["reviewer2"]),
    )
    assert lost.status_code == 409


def test_concurrent_claim_exactly_one_wins(engine):
    """Persistence-truth: atomic UPDATE … WHERE claimed_by IS NULL under two sessions."""
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionLocal() as db:
        practice = Practice(id=uuid.uuid4(), name="Race Practice")
        member = Member(id=uuid.uuid4(), external_id=f"R-{uuid.uuid4().hex[:6]}", full_name="R")
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
            email=f"o-{uuid.uuid4().hex[:6]}@ex.com",
            role=UserRole.provider_office,
            practice_id=practice.id,
            display_name="O",
        )
        r1 = User(
            id=uuid.uuid4(),
            email=f"r1-{uuid.uuid4().hex[:6]}@ex.com",
            role=UserRole.reviewer,
            display_name="R1",
        )
        r2 = User(
            id=uuid.uuid4(),
            email=f"r2-{uuid.uuid4().hex[:6]}@ex.com",
            role=UserRole.reviewer,
            display_name="R2",
        )
        db.add_all([office, r1, r2])
        db.flush()
        request = PriorAuthRequest(
            id=uuid.uuid4(),
            member_id=member.id,
            practice_id=practice.id,
            submitted_by_user_id=office.id,
            diagnosis_icd10="J06.9",
            date_of_service=today,
            status=RequestStatus.submitted,
        )
        request.procedures.append(PriorAuthProcedure(code="99213", units=1, sequence=1))
        db.add(request)
        db.commit()
        request_id = request.id
        r1_id, r2_id = r1.id, r2.id

    outcomes: list[str] = []
    barrier = threading.Barrier(2)
    lock = threading.Lock()

    def attempt(user_id: uuid.UUID) -> None:
        with SessionLocal() as session:
            ctx = UserContext(user_id=user_id, role=UserRole.reviewer)
            barrier.wait(timeout=5)
            try:
                claim_request(session, ctx, request_id)
                with lock:
                    outcomes.append("won")
            except ConflictError:
                with lock:
                    outcomes.append("lost")

    threads = [
        threading.Thread(target=attempt, args=(r1_id,)),
        threading.Thread(target=attempt, args=(r2_id,)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert sorted(outcomes) == ["lost", "won"], outcomes
    with SessionLocal() as db:
        row = db.get(PriorAuthRequest, request_id)
        assert row is not None
        assert row.status == RequestStatus.in_review
        assert row.claimed_by_user_id in {r1_id, r2_id}
