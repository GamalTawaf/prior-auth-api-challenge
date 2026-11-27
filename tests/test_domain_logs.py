"""Domain + worker lifecycle logs (ids only; no clinical notes / denial text)."""

from __future__ import annotations

import logging

from app.outbox.service import process_batch
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


def _domain_messages(caplog) -> list[str]:
    """Only app.prior_auth / app.intake / app.outbox records (ignore SQLA SQL noise)."""
    return [
        r.getMessage()
        for r in caplog.records
        if r.name.startswith(("app.prior_auth", "app.intake", "app.outbox"))
    ]


def test_submit_claim_conflict_reassign_decide_logs(client: TestClient, caplog):
    # Pin domain loggers so a prior test's root WARNING (LOG_LEVEL) cannot hide INFO.
    loggers = (
        "app.prior_auth.services.submit",
        "app.prior_auth.services.claim",
        "app.prior_auth.services.decide",
        "app.prior_auth.services.reassign",
    )
    practice_id = str(client.seed["practice"].uuid)
    member_id = str(client.seed["member"].uuid)
    reviewer_id = str(client.seed["reviewer"].uuid)

    with caplog.at_level(logging.INFO):
        for name in loggers:
            logging.getLogger(name).setLevel(logging.INFO)
        body = submit_ok(client)
        msgs = _domain_messages(caplog)
        request_id = body["uuid"]
        submitted = (
            f"prior auth submitted request_id={request_id} "
            f"practice_id={practice_id} member_id={member_id} procedures=1"
        )
        assert submitted in msgs
        joined = "\n".join(msgs)
        assert "clinical_note" not in joined.lower()

        claimed = claim_as(client, request_id)
        assert claimed.status_code == 200
        claimed_msg = f"prior auth claimed request_id={request_id} reviewer_id={reviewer_id}"
        assert claimed_msg in _domain_messages(caplog)

        conflict = claim_as(client, request_id)
        assert conflict.status_code == 409
        conflict_msg = f"claim conflict request_id={request_id} reviewer_id={reviewer_id}"
        assert conflict_msg in _domain_messages(caplog)

        reassigned = reassign_as(client, request_id, client.seed["reviewer"].uuid)
        assert reassigned.status_code == 200
        reassigned_msg = (
            f"prior auth reassigned request_id={request_id} from={reviewer_id} to={reviewer_id}"
        )
        assert reassigned_msg in _domain_messages(caplog)

        data = submit_and_claim(client)
        outcomes = approve_all_outcomes(data["procedures"])
        decided = decide_as(client, data["uuid"], outcomes)
        assert decided.status_code == 200
        decided_id = data["uuid"]
        decided_msg = (
            f"prior auth decided request_id={decided_id} "
            f"reviewer_id={reviewer_id} approved=1 denied=0"
        )
        assert decided_msg in _domain_messages(caplog)

        # denied>0 so mutants of the denied sum / "denied" compare change the message
        denied_data = submit_and_claim(client)
        denied_outcomes = [
            {
                "procedure_id": denied_data["procedures"][0]["uuid"],
                "decision": "denied",
                "denial_reason": "not medically necessary",
            }
        ]
        denied_resp = decide_as(client, denied_data["uuid"], denied_outcomes)
        assert denied_resp.status_code == 200
        denied_id = denied_data["uuid"]
        denied_msg = (
            f"prior auth decided request_id={denied_id} "
            f"reviewer_id={reviewer_id} approved=0 denied=1"
        )
        assert denied_msg in _domain_messages(caplog)
        assert all("denial_reason" not in m for m in _domain_messages(caplog))
        assert all("not medically necessary" not in m for m in _domain_messages(caplog))


def test_intake_rejection_logs_without_payload(client: TestClient, caplog):
    practice_id = str(client.seed["practice"].uuid)
    with caplog.at_level(logging.WARNING, logger="app.intake.service"):
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
    correlation_id = bad.json()["correlation_id"]
    expected = (
        f"intake rejected correlation_id={correlation_id} "
        f"practice_id={practice_id} fields=['member_id']"
    )
    assert expected in _domain_messages(caplog)
    assert all("secret note must not appear" not in m for m in _domain_messages(caplog))


def test_outbox_worker_and_send_failure_logs(client: TestClient, db: Session, monkeypatch, caplog):
    data = submit_and_claim(client)
    decided = decide_as(client, data["uuid"], approve_all_outcomes(data["procedures"]))
    assert decided.status_code == 200

    def boom(_to: str, _subject: str, _text: str) -> None:
        raise RuntimeError("smtp down")

    with caplog.at_level(logging.WARNING, logger="app.outbox.service"):
        n = process_batch(db, send_fn=boom)
    assert n == 1
    fail_msgs = [
        m for m in _domain_messages(caplog) if m.startswith("outbox send failed event_id=")
    ]
    assert len(fail_msgs) == 1
    assert fail_msgs[0].endswith("error=smtp down")

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
    start_msgs = [
        m for m in _domain_messages(caplog) if m.startswith("outbox worker starting poll_seconds=")
    ]
    assert len(start_msgs) == 1

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
    assert "outbox delivered batch_size=2" in _domain_messages(caplog)
