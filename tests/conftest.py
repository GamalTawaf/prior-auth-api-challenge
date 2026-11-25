from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://prior:prior@localhost:5432/prior_auth")
os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-minimum!!!!")

from app.audit import models as _audit_models  # noqa: F401
from app.clock import get_today
from app.config import settings
from app.db import Base, get_db
from app.identity.auth import mint_token
from app.identity.models import User, UserRole
from app.intake import models as _intake_models  # noqa: F401
from app.main import app
from app.master_data.models import (
    Coverage,
    Member,
    PatientPracticeLink,
    Practice,
    ReviewerMemberConflict,
)
from app.prior_auth import models as _pa_models  # noqa: F401


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(settings.database_url, pool_pre_ping=True)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(eng)
    yield eng
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture
def db(engine) -> Generator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, autoflush=False, expire_on_commit=False)
    session = SessionLocal()
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def seed_data(db: Session) -> dict:
    practice = Practice(id=uuid.uuid4(), name="Test Practice")
    member = Member(
        id=uuid.uuid4(),
        external_id=f"M-{uuid.uuid4().hex[:8]}",
        full_name="Pat Member",
    )
    unlinked = Member(
        id=uuid.uuid4(), external_id=f"U-{uuid.uuid4().hex[:8]}", full_name="Unlinked"
    )
    db.add_all([practice, member, unlinked])
    db.flush()
    db.add(PatientPracticeLink(member_id=member.id, practice_id=practice.id))
    today = get_today()
    db.add(
        Coverage(
            member_id=member.id,
            payer_name="Payer",
            effective_from=today - timedelta(days=10),
            effective_to=today + timedelta(days=400),
        )
    )
    office = User(
        id=uuid.uuid4(),
        email=f"office-{uuid.uuid4().hex[:6]}@ex.com",
        role=UserRole.provider_office,
        practice_id=practice.id,
        display_name="Office",
    )
    reviewer = User(
        id=uuid.uuid4(),
        email=f"rev-{uuid.uuid4().hex[:6]}@ex.com",
        role=UserRole.reviewer,
        display_name="Reviewer",
    )
    reviewer2 = User(
        id=uuid.uuid4(),
        email=f"rev2-{uuid.uuid4().hex[:6]}@ex.com",
        role=UserRole.reviewer,
        display_name="Reviewer2",
    )
    reviewer_coi = User(
        id=uuid.uuid4(),
        email=f"coi-{uuid.uuid4().hex[:6]}@ex.com",
        role=UserRole.reviewer,
        display_name="COI Reviewer",
    )
    admin = User(
        id=uuid.uuid4(),
        email=f"admin-{uuid.uuid4().hex[:6]}@ex.com",
        role=UserRole.ops_admin,
        display_name="Admin",
    )
    member_user = User(
        id=uuid.uuid4(),
        email=f"mem-{uuid.uuid4().hex[:6]}@ex.com",
        role=UserRole.member,
        member_id=member.id,
        display_name="Member",
    )
    db.add_all([office, reviewer, reviewer2, reviewer_coi, admin, member_user])
    db.flush()
    db.add(ReviewerMemberConflict(reviewer_user_id=reviewer_coi.id, member_id=member.id))
    db.flush()
    return {
        "practice": practice,
        "member": member,
        "unlinked": unlinked,
        "office": office,
        "reviewer": reviewer,
        "reviewer2": reviewer2,
        "reviewer_coi": reviewer_coi,
        "admin": admin,
        "member_user": member_user,
        "tokens": {
            "office": mint_token(office),
            "reviewer": mint_token(reviewer),
            "reviewer2": mint_token(reviewer2),
            "reviewer_coi": mint_token(reviewer_coi),
            "admin": mint_token(admin),
            "member": mint_token(member_user),
        },
    }


@pytest.fixture
def client(db: Session, seed_data: dict) -> Generator[TestClient]:
    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        c.seed = seed_data  # type: ignore[attr-defined]
        yield c
    app.dependency_overrides.clear()


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def valid_submit_body(seed: dict, **overrides) -> dict:
    from app.clock import get_today

    body = {
        "member_id": str(seed["member"].id),
        "diagnosis_icd10": "J06.9",
        "date_of_service": get_today().isoformat(),
        "clinical_note": "Patient needs procedure",
        "procedures": [{"code": "99213", "units": 1}],
    }
    body.update(overrides)
    return body
