from fastapi.testclient import TestClient

from tests.conftest import auth, valid_submit_body


def test_coi_reviewer_cannot_claim(client: TestClient):
    created = client.post(
        "/v1/prior-auths",
        headers=auth(client.seed["tokens"]["office"]),
        json=valid_submit_body(client.seed),
    )
    rid = created.json()["id"]
    response = client.post(
        f"/v1/prior-auths/{rid}/claim",
        headers=auth(client.seed["tokens"]["reviewer_coi"]),
    )
    assert response.status_code == 403
    assert "conflict" in response.json()["detail"].lower()
