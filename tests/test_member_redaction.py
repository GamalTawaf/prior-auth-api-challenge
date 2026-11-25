from fastapi.testclient import TestClient

from tests.conftest import auth, valid_submit_body


def test_member_get_strips_note_and_denial_reason(client: TestClient):
    created = client.post(
        "/v1/prior-auths",
        headers=auth(client.seed["tokens"]["office"]),
        json=valid_submit_body(client.seed, clinical_note="SECRET NOTE"),
    )
    rid = created.json()["id"]
    client.post(f"/v1/prior-auths/{rid}/claim", headers=auth(client.seed["tokens"]["reviewer"]))
    detail = client.get(f"/v1/prior-auths/{rid}", headers=auth(client.seed["tokens"]["reviewer"]))
    proc_id = detail.json()["procedures"][0]["id"]
    client.post(
        f"/v1/prior-auths/{rid}/decision",
        headers=auth(client.seed["tokens"]["reviewer"]),
        json={
            "outcomes": [
                {
                    "procedure_id": proc_id,
                    "decision": "denied",
                    "denial_reason": "Not covered experimentally",
                }
            ]
        },
    )

    member = client.get(
        f"/v1/me/prior-auths/{rid}",
        headers=auth(client.seed["tokens"]["member"]),
    )
    assert member.status_code == 200, member.text
    body = member.json()
    assert "clinical_note" not in body
    assert "denial_reason" not in str(body)
    assert body["procedures"][0]["status"] == "not_approved"

    listed = client.get("/v1/me/prior-auths", headers=auth(client.seed["tokens"]["member"]))
    assert listed.status_code == 200
    assert any(r["id"] == rid for r in listed.json())


def test_admin_audit_trail(client: TestClient):
    created = client.post(
        "/v1/prior-auths",
        headers=auth(client.seed["tokens"]["office"]),
        json=valid_submit_body(client.seed),
    )
    rid = created.json()["id"]
    client.post(f"/v1/prior-auths/{rid}/claim", headers=auth(client.seed["tokens"]["reviewer"]))
    audit = client.get(
        f"/v1/prior-auths/{rid}/audit",
        headers=auth(client.seed["tokens"]["admin"]),
    )
    assert audit.status_code == 200
    actions = {e["action"] for e in audit.json()}
    assert "submit" in actions
    assert "claim" in actions
