"""Domain + worker lifecycle logs (ids only; no clinical notes / denial text)."""

from __future__ import annotations

import logging

from app.outbox.services import process_batch
from app.outbox.worker import main, run_once
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import (
    approve_all_outcomes,
    claim_as,
    decide_as,
    reassign_as,
    role_headers,
    submit_and_claim,
    submit_ok,
)


def _domain_messages(caplog) -> str:
    """Only app.prior_auth / app.intake / app.outbox records (ignore SQLA SQL noise)."""
    parts = [
        r.getMessage()
        for r in caplog.records
        if r.name.startswith(("app.prior_auth", "app.intake", "app.outbox"))
    ]
    return "\n".join(parts)


def test_submit_claim_conflict_reassign_decide_logs(client: TestClient, caplog):
    # Pin domain loggers so a prior test's root WARNING (LOG_LEVEL) cannot hide INFO.
    loggers = (
        "app.prior_auth.services.submit",
        "app.prior_auth.services.claim",
        "app.prior_auth.services.decide",
        "app.prior_auth.services.reassign",
    )
    with caplog.at_level(logging.INFO):
        for name in loggers:
            logging.getLogger(name).setLevel(logging.INFO)
        body = submit_ok(client)
        domain = _domain_messages(caplog)
        assert "prior auth submitted request_id=" in domain
        assert body["uuid"] in domain
        assert "clinical_note" not in domain.lower()

        claimed = claim_as(client, body["uuid"])
        assert claimed.status_code == 200
        domain = _domain_messages(caplog)
        assert "prior auth claimed request_id=" in domain

        conflict = claim_as(client, body["uuid"])
        assert conflict.status_code == 409
        domain = _domain_messages(caplog)
        assert "claim conflict request_id=" in domain

        reassigned = reassign_as(client, body["uuid"], client.seed["reviewer"].uuid)
        assert reassigned.status_code == 200
        domain = _domain_messages(caplog)
        assert "prior auth reassigned request_id=" in domain

        data = submit_and_claim(client)
        outcomes = approve_all_outcomes(data["procedures"])
        decided = decide_as(client, data["uuid"], outcomes)
        assert decided.status_code == 200
        domain = _domain_messages(caplog)
        assert "prior auth decided request_id=" in domain
        assert "approved=" in domain
        assert "denial_reason" not in domain


def test_intake_rejection_logs_without_payload(client: TestClient, caplog):
    with caplog.at_level(logging.WARNING, logger="app.intake.persist"):
        bad = client.post(
            "/v1/prior-auths",
            headers=role_headers(client, "office"),
            json={
                "member_id": "00000000-0000-0000-0000-000000000099",
                "diagnosis_icd10": "M54.5",
                "date_of_service": "2099-01-01",
                "clinical_note": "secret note must not appear",
                "procedures": [{"code": "97110", "units": 1}],
            },
        )
    assert bad.status_code == 422
    assert "intake rejected correlation_id=" in caplog.text
    assert "secret note must not appear" not in caplog.text


def test_outbox_worker_and_send_failure_logs(client: TestClient, db: Session, monkeypatch, caplog):
    data = submit_and_claim(client)
    decided = decide_as(client, data["uuid"], approve_all_outcomes(data["procedures"]))
    assert decided.status_code == 200

    def boom(_to: str, _subject: str, _text: str) -> None:
        raise RuntimeError("smtp down")

    with caplog.at_level(logging.WARNING, logger="app.outbox.services"):
        n = process_batch(db, send_fn=boom)
    assert n == 1
    assert "outbox send failed event_id=" in caplog.text
    assert "smtp down" in caplog.text

    configured: list[int] = []

    def fake_configure() -> None:
        configured.append(1)

    monkeypatch.setattr("app.outbox.worker.configure_telemetry", fake_configure)

    def fake_loop() -> None:
        return None

    monkeypatch.setattr("app.outbox.worker.run_loop", fake_loop)
    with caplog.at_level(logging.INFO, logger="app.outbox.worker"):
        main()
    assert configured == [1]
    assert "outbox worker starting poll_seconds=" in caplog.text

    class _Sess:
        def __enter__(self):
            return db

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr("app.outbox.worker.SessionLocal", _Sess)

    def fake_process(_db):
        return 2

    monkeypatch.setattr("app.outbox.worker.process_batch", fake_process)
    with caplog.at_level(logging.INFO, logger="app.outbox.worker"):
        delivered = run_once()
    assert delivered == 2
    assert "outbox delivered batch_size=2" in caplog.text
