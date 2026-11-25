from fastapi.testclient import TestClient

from tests.conftest import auth, valid_submit_body


def _submit_and_claim(client: TestClient) -> dict:
    created = client.post(
        "/v1/prior-auths",
        headers=auth(client.seed["tokens"]["office"]),
        json=valid_submit_body(
            client.seed,
            procedures=[{"code": "99213", "units": 1}, {"code": "99214", "units": 2}],
        ),
    )
    assert created.status_code == 201
    rid = created.json()["id"]
    claimed = client.post(
        f"/v1/prior-auths/{rid}/claim",
        headers=auth(client.seed["tokens"]["reviewer"]),
    )
    assert claimed.status_code == 200
    return claimed.json()


def test_decide_missing_procedure_422(client: TestClient):
    data = _submit_and_claim(client)
    only_one = data["procedures"][0]
    response = client.post(
        f"/v1/prior-auths/{data['id']}/decision",
        headers=auth(client.seed["tokens"]["reviewer"]),
        json={
            "outcomes": [
                {"procedure_id": only_one["id"], "decision": "approved"},
            ]
        },
    )
    assert response.status_code == 422
    assert any(e["error_code"] == "procedures_incomplete" for e in response.json()["errors"])


def test_deny_without_reason_422(client: TestClient):
    data = _submit_and_claim(client)
    outcomes = [
        {"procedure_id": p["id"], "decision": "denied", "denial_reason": None}
        for p in data["procedures"]
    ]
    response = client.post(
        f"/v1/prior-auths/{data['id']}/decision",
        headers=auth(client.seed["tokens"]["reviewer"]),
        json={"outcomes": outcomes},
    )
    assert response.status_code == 422
    assert any(e["error_code"] == "denial_reason_required" for e in response.json()["errors"])


def test_decide_happy_and_terminal(client: TestClient):
    data = _submit_and_claim(client)
    outcomes = [
        {"procedure_id": data["procedures"][0]["id"], "decision": "approved"},
        {
            "procedure_id": data["procedures"][1]["id"],
            "decision": "denied",
            "denial_reason": "Not medically necessary",
        },
    ]
    decided = client.post(
        f"/v1/prior-auths/{data['id']}/decision",
        headers=auth(client.seed["tokens"]["reviewer"]),
        json={"outcomes": outcomes},
    )
    assert decided.status_code == 200, decided.text
    body = decided.json()
    assert body["status"] == "decided"
    assert body["decided_by_user_id"] == str(client.seed["reviewer"].id)

    again = client.post(
        f"/v1/prior-auths/{data['id']}/decision",
        headers=auth(client.seed["tokens"]["reviewer"]),
        json={"outcomes": outcomes},
    )
    assert again.status_code == 409

    reassign = client.post(
        f"/v1/prior-auths/{data['id']}/reassign",
        headers=auth(client.seed["tokens"]["admin"]),
        json={"reviewer_id": str(client.seed["reviewer2"].id)},
    )
    assert reassign.status_code == 409


def test_admin_reassign_while_in_review(client: TestClient):
    data = _submit_and_claim(client)
    response = client.post(
        f"/v1/prior-auths/{data['id']}/reassign",
        headers=auth(client.seed["tokens"]["admin"]),
        json={"reviewer_id": str(client.seed["reviewer2"].id)},
    )
    assert response.status_code == 200
    assert response.json()["claimed_by_user_id"] == str(client.seed["reviewer2"].id)
