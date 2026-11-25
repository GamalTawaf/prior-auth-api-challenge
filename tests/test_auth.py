from app.identity.auth import mint_token, require_role
from app.identity.models import UserRole
from app.main import app
from fastapi.testclient import TestClient

from tests.conftest import auth


def test_seed_jwt_authorizes_protected_list(client: TestClient):
    token = client.seed["tokens"]["office"]
    response = client.get("/v1/prior-auths", headers=auth(token))
    assert response.status_code == 200
    assert response.json() == []


def test_missing_token_401(client: TestClient):
    response = client.get("/v1/prior-auths")
    assert response.status_code == 401


def test_wrong_role_403(client: TestClient):
    token = client.seed["tokens"]["member"]
    response = client.get("/v1/prior-auths", headers=auth(token))
    assert response.status_code == 403


def test_require_role_helper_rejects(client: TestClient):
    token = client.seed["tokens"]["office"]
    response = client.get("/v1/review-queue", headers=auth(token))
    assert response.status_code == 403
    assert require_role(UserRole.reviewer)
    assert app.title
    _ = mint_token(client.seed["office"])


def test_expired_token_401(client: TestClient):
    token = mint_token(client.seed["office"], hours=-1)
    response = client.get("/v1/prior-auths", headers=auth(token))
    assert response.status_code == 401
