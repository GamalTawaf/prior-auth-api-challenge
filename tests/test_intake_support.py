from fastapi.testclient import TestClient

from tests.conftest import auth, valid_submit_body


def test_support_lookup_by_correlation_id(client: TestClient):
    body = valid_submit_body(client.seed, member_id=str(client.seed["unlinked"].id))
    failed = client.post(
        "/v1/prior-auths",
        headers=auth(client.seed["tokens"]["office"]),
        json=body,
    )
    assert failed.status_code == 422
    cid = failed.json()["correlation_id"]

    support = client.get(
        f"/v1/support/intake-rejections/{cid}",
        headers=auth(client.seed["tokens"]["office"]),
    )
    assert support.status_code == 200, support.text
    data = support.json()
    assert data["correlation_id"] == cid
    assert data["field_errors"]

    admin = client.get(
        f"/v1/support/intake-rejections/{cid}",
        headers=auth(client.seed["tokens"]["admin"]),
    )
    assert admin.status_code == 200

    missing = client.get(
        "/v1/support/intake-rejections/does-not-exist",
        headers=auth(client.seed["tokens"]["office"]),
    )
    assert missing.status_code == 404
