from fastapi.testclient import TestClient

from tests.conftest import (
    TWO_PROCEDURES,
    assert_has_error_code,
    decide_as,
    reassign_as,
    submit_and_claim,
)


def test_decide_missing_procedure_422(client: TestClient):
    data = submit_and_claim(client, procedures=TWO_PROCEDURES)
    only_one = data["procedures"][0]
    response = decide_as(
        client,
        data["id"],
        [{"procedure_id": only_one["id"], "decision": "approved"}],
    )
    assert_has_error_code(
        response,
        "procedures_incomplete",
        field="outcomes",
        message="Decision must cover every procedure exactly once",
    )


def test_deny_without_reason_422(client: TestClient):
    data = submit_and_claim(client, procedures=TWO_PROCEDURES)
    outcomes = [
        {"procedure_id": p["id"], "decision": "denied", "denial_reason": None}
        for p in data["procedures"]
    ]
    response = decide_as(client, data["id"], outcomes)
    assert_has_error_code(
        response,
        "denial_reason_required",
        message="Denial reason is required when denying",
    )


def test_decide_happy_and_terminal(client: TestClient):
    data = submit_and_claim(client, procedures=TWO_PROCEDURES)
    outcomes = [
        {"procedure_id": data["procedures"][0]["id"], "decision": "approved"},
        {
            "procedure_id": data["procedures"][1]["id"],
            "decision": "denied",
            "denial_reason": "Not medically necessary",
        },
    ]
    decided = decide_as(client, data["id"], outcomes)
    assert decided.status_code == 200, decided.text
    body = decided.json()
    assert body["status"] == "decided"
    assert body["decided_by_user_id"] == str(client.seed["reviewer"].id)

    again = decide_as(client, data["id"], outcomes)
    assert again.status_code == 409

    reassign = reassign_as(client, data["id"], client.seed["reviewer2"].id)
    assert reassign.status_code == 409


def test_admin_reassign_while_in_review(client: TestClient):
    data = submit_and_claim(client, procedures=TWO_PROCEDURES)
    response = reassign_as(client, data["id"], client.seed["reviewer2"].id)
    assert response.status_code == 200
    assert response.json()["claimed_by_user_id"] == str(client.seed["reviewer2"].id)
