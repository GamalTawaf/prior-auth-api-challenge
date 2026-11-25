#!/usr/bin/env python3
"""Build Postman Collection v2.1 + environment from live FastAPI OpenAPI."""

from __future__ import annotations

import json
from pathlib import Path

from app.identity.auth import mint_token
from app.identity.models import User, UserRole
from app.main import app

from scripts.seed import (
    ADMIN_ID,
    MEMBER_ID,
    MEMBER_USER_ID,
    OFFICE_ID,
    PRACTICE_ID,
    REVIEWER_COI_ID,
    REVIEWER_ID,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "postman"


def _items_from_openapi(spec: dict) -> list[dict]:
    items: list[dict] = []
    for path, methods in spec.get("paths", {}).items():
        for method, op in methods.items():
            if method.startswith("x-"):
                continue
            name = op.get("summary") or f"{method.upper()} {path}"
            item = {
                "name": name,
                "request": {
                    "method": method.upper(),
                    "header": [{"key": "Content-Type", "value": "application/json"}],
                    "url": {
                        "raw": "{{base_url}}" + path,
                        "host": ["{{base_url}}"],
                        "path": [p for p in path.strip("/").split("/") if p],
                    },
                    "auth": {
                        "type": "bearer",
                        "bearer": [{"key": "token", "value": "{{token}}", "type": "string"}],
                    },
                },
            }
            if "requestBody" in op:
                item["request"]["body"] = {
                    "mode": "raw",
                    "raw": "{}",
                    "options": {"raw": {"language": "json"}},
                }
            items.append(item)
    return items


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    spec = app.openapi()
    collection = {
        "info": {
            "name": "Prior Auth API",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "description": "Generated from FastAPI OpenAPI — do not hand-edit; regenerate.",
        },
        "item": _items_from_openapi(spec),
        "auth": {
            "type": "bearer",
            "bearer": [{"key": "token", "value": "{{token}}", "type": "string"}],
        },
    }

    # Stable seed users (IDs match scripts/seed.py); tokens minted with current JWT_SECRET
    users = {
        "office_token": User(
            id=OFFICE_ID,
            email="office@example.com",
            role=UserRole.provider_office,
            practice_id=PRACTICE_ID,
            display_name="o",
        ),
        "reviewer_token": User(
            id=REVIEWER_ID, email="reviewer@example.com", role=UserRole.reviewer, display_name="r"
        ),
        "reviewer_coi_token": User(
            id=REVIEWER_COI_ID,
            email="reviewer.coi@example.com",
            role=UserRole.reviewer,
            display_name="c",
        ),
        "admin_token": User(
            id=ADMIN_ID, email="admin@example.com", role=UserRole.ops_admin, display_name="a"
        ),
        "member_token": User(
            id=MEMBER_USER_ID,
            email="member@example.com",
            role=UserRole.member,
            member_id=MEMBER_ID,
            display_name="m",
        ),
    }
    env_values = [
        {"key": "base_url", "value": "http://localhost:8000", "enabled": True},
        {"key": "token", "value": "{{office_token}}", "enabled": True},
    ]
    for key, user in users.items():
        env_values.append({"key": key, "value": mint_token(user), "enabled": True})

    environment = {
        "id": "prior-auth-local",
        "name": "Prior Auth Local",
        "values": env_values,
    }

    (OUT / "Prior_Auth_API.postman_collection.json").write_text(json.dumps(collection, indent=2))
    (OUT / "Prior_Auth_API.postman_environment.json").write_text(json.dumps(environment, indent=2))
    paths = {item["request"]["url"]["raw"] for item in collection["item"]}
    required = [
        "{{base_url}}/v1/prior-auths",
        "{{base_url}}/v1/prior-auths/{request_id}/claim",
        "{{base_url}}/v1/prior-auths/{request_id}/decision",
        "{{base_url}}/v1/me/prior-auths",
        "{{base_url}}/v1/support/intake-rejections/{correlation_id}",
    ]
    for req in required:
        assert any(req in p or p == req for p in paths) or req in paths, paths
    print(f"Wrote {len(collection['item'])} requests to {OUT}")


if __name__ == "__main__":
    main()
