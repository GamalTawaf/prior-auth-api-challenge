#!/usr/bin/env -S uv run python
"""Build Postman Collection v2.1 + environment from live FastAPI OpenAPI."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.clock import get_today
from app.identity.auth import mint_token
from app.identity.models import User, UserRole
from app.main import app

from scripts.seed import (
    ADMIN_ID,
    AUDITOR_ID,
    MEMBER_ID,
    MEMBER_UNLINKED_ID,
    MEMBER_USER_ID,
    OFFICE_ID,
    PRACTICE_ID,
    REVIEWER_COI_ID,
    REVIEWER_ID,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "postman"

_PATH_PARAM = re.compile(r"\{([^}/]+)\}")

# Ready-to-send demo payloads. Env vars are prefilled from seed; paste ids after submit.
_DEMO_BODIES: dict[tuple[str, str], dict[str, Any]] = {
    ("post", "/v1/prior-auths"): {
        "member_id": "{{member_id}}",
        "diagnosis_icd10": "J06.9",
        "date_of_service": get_today().isoformat(),
        "clinical_note": "Demo clinical note for Postman",
        "procedures": [{"code": "99213", "units": 1}],
    },
    ("post", "/v1/prior-auths/{request_id}/decision"): {
        "outcomes": [
            {
                "procedure_id": "{{procedure_id}}",
                "decision": "approved",
            }
        ],
    },
    ("post", "/v1/prior-auths/{request_id}/reassign"): {
        "reviewer_id": "{{reviewer_id}}",
    },
}

# Bearer env var per operationId / path+method (seed role that can call the route).
_TOKEN_FOR: dict[tuple[str, str], str] = {
    ("post", "/v1/prior-auths"): "{{office_token}}",
    ("get", "/v1/prior-auths"): "{{office_token}}",
    ("get", "/v1/prior-auths/{request_id}"): "{{office_token}}",
    ("get", "/v1/review-queue"): "{{reviewer_token}}",
    ("post", "/v1/prior-auths/{request_id}/claim"): "{{reviewer_token}}",
    ("post", "/v1/prior-auths/{request_id}/decision"): "{{reviewer_token}}",
    ("post", "/v1/prior-auths/{request_id}/reassign"): "{{admin_token}}",
    ("get", "/v1/prior-auths/{request_id}/audit"): "{{auditor_token}}",
    ("get", "/v1/reviewers/workload"): "{{admin_token}}",
    ("get", "/v1/me/prior-auths"): "{{member_token}}",
    ("get", "/v1/me/prior-auths/{request_id}"): "{{member_token}}",
    ("get", "/v1/support/intake-rejections/{correlation_id}"): "{{office_token}}",
}

_PATH_VAR_DEFAULTS: dict[str, str] = {
    "request_id": "{{request_id}}",
    "correlation_id": "{{correlation_id}}",
}


def _bearer(token_expr: str) -> dict[str, Any]:
    return {
        "type": "bearer",
        "bearer": [{"key": "token", "value": token_expr, "type": "string"}],
    }


def _postman_url(path: str) -> dict[str, Any]:
    """Turn `/v1/foo/{id}` into Postman path segments + variables."""
    segments: list[str] = []
    variables: list[dict[str, str]] = []
    raw_parts: list[str] = []
    for part in path.strip("/").split("/"):
        if not part:
            continue
        match = _PATH_PARAM.fullmatch(part)
        if match:
            name = match.group(1)
            segments.append(f":{name}")
            raw_parts.append("{{" + name + "}}")
            variables.append(
                {
                    "key": name,
                    "value": _PATH_VAR_DEFAULTS.get(name, "{{" + name + "}}"),
                }
            )
        else:
            segments.append(part)
            raw_parts.append(part)
    url: dict[str, Any] = {
        "raw": "{{base_url}}/" + "/".join(raw_parts),
        "host": ["{{base_url}}"],
        "path": segments,
    }
    if variables:
        url["variable"] = variables
    return url


def _example_from_schema(schema: dict[str, Any], components: dict[str, Any]) -> Any:
    """Best-effort JSON example from an OpenAPI schema (for unknown bodies)."""
    if "$ref" in schema:
        ref = schema["$ref"].rsplit("/", 1)[-1]
        return _example_from_schema(components.get("schemas", {}).get(ref, {}), components)
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    schema_type = schema.get("type")
    if schema.get("enum"):
        return schema["enum"][0]
    if schema_type == "object" or "properties" in schema:
        props = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        out: dict[str, Any] = {}
        for key, prop in props.items():
            if key in required or prop.get("type") in {"object", "array"}:
                out[key] = _example_from_schema(prop, components)
            elif "default" in prop:
                out[key] = prop["default"]
            elif key in required:
                out[key] = _example_from_schema(prop, components)
        for key in required:
            out.setdefault(key, _example_from_schema(props.get(key, {}), components))
        return out
    if schema_type == "array":
        item = _example_from_schema(schema.get("items") or {}, components)
        return [item]
    if schema_type == "string":
        fmt = schema.get("format")
        if fmt == "uuid":
            return str(MEMBER_ID)
        if fmt == "date":
            return get_today().isoformat()
        if fmt == "date-time":
            return f"{get_today().isoformat()}T12:00:00Z"
        return "string"
    if schema_type == "integer":
        return 1
    if schema_type == "number":
        return 1.0
    if schema_type == "boolean":
        return True
    return None


def _body_for(method: str, path: str, op: dict[str, Any], components: dict[str, Any]) -> str:
    key = (method.lower(), path)
    if key in _DEMO_BODIES:
        return json.dumps(_DEMO_BODIES[key], indent=2)
    body = op.get("requestBody") or {}
    content = body.get("content") or {}
    app_json = content.get("application/json") or next(iter(content.values()), None)
    if not app_json:
        return "{}"
    if "example" in app_json:
        return json.dumps(app_json["example"], indent=2)
    examples = app_json.get("examples") or {}
    if examples:
        first = next(iter(examples.values()))
        if isinstance(first, dict) and "value" in first:
            return json.dumps(first["value"], indent=2)
    schema = app_json.get("schema") or {}
    generated = _example_from_schema(schema, components)
    return json.dumps(generated if generated is not None else {}, indent=2)


def _query_defaults(path: str, method: str) -> list[dict[str, Any]]:
    """Optional query params pre-filled for list endpoints."""
    if method.lower() != "get":
        return []
    if path in {"/v1/prior-auths", "/v1/review-queue", "/v1/me/prior-auths"}:
        return [
            {"key": "limit", "value": "20", "enabled": True},
            {"key": "after", "value": "", "description": "optional cursor id", "enabled": False},
        ]
    return []


def _items_from_openapi(spec: dict[str, Any]) -> list[dict[str, Any]]:
    components = spec.get("components") or {}
    items: list[dict[str, Any]] = []
    for path, methods in (spec.get("paths") or {}).items():
        for method, op in methods.items():
            if method.startswith("x-") or not isinstance(op, dict):
                continue
            name = op.get("summary") or f"{method.upper()} {path}"
            token = _TOKEN_FOR.get((method.lower(), path), "{{token}}")
            request: dict[str, Any] = {
                "method": method.upper(),
                "header": [{"key": "Content-Type", "value": "application/json"}],
                "url": _postman_url(path),
                "auth": _bearer(token),
                "description": (
                    op.get("description")
                    or "Generated demo request — edit env vars (request_id, procedure_id) after submit."
                ),
            }
            query = _query_defaults(path, method)
            if query:
                request["url"]["query"] = query
            if "requestBody" in op:
                request["body"] = {
                    "mode": "raw",
                    "raw": _body_for(method, path, op, components),
                    "options": {"raw": {"language": "json"}},
                }
            items.append({"name": name, "request": request})
    return items


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    spec = app.openapi()
    items = _items_from_openapi(spec)
    collection = {
        "info": {
            "name": "Prior Auth API",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "description": (
                "Generated from FastAPI OpenAPI with seed demo bodies. "
                "Run `scripts/seed.py`, import env, then Submit → paste id into "
                "`request_id` / `procedure_id` for claim/decide. Do not hand-edit; regenerate."
            ),
        },
        "item": items,
        "auth": _bearer("{{token}}"),
        "variable": [
            {
                "key": "request_id",
                "value": "00000000-0000-4000-8000-000000000001",
            },
            {
                "key": "procedure_id",
                "value": "00000000-0000-4000-8000-000000000002",
            },
            {"key": "correlation_id", "value": "demo-correlation"},
        ],
    }

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
        "auditor_token": User(
            id=AUDITOR_ID,
            email="auditor@example.com",
            role=UserRole.auditor,
            display_name="au",
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
        {"key": "member_id", "value": str(MEMBER_ID), "enabled": True},
        {"key": "member_unlinked_id", "value": str(MEMBER_UNLINKED_ID), "enabled": True},
        {"key": "practice_id", "value": str(PRACTICE_ID), "enabled": True},
        {"key": "reviewer_id", "value": str(REVIEWER_ID), "enabled": True},
        {
            "key": "request_id",
            "value": "00000000-0000-4000-8000-000000000001",
            "enabled": True,
            "description": "Replace with Prior Auth id from Submit response",
        },
        {
            "key": "procedure_id",
            "value": "00000000-0000-4000-8000-000000000002",
            "enabled": True,
            "description": "Replace with procedures[0].id from Submit/Claim response",
        },
        {
            "key": "correlation_id",
            "value": "demo-correlation",
            "enabled": True,
            "description": "From failed submit response / IntakeRejection",
        },
    ]
    for key, user in users.items():
        env_values.append({"key": key, "value": mint_token(user), "enabled": True})

    environment = {
        "id": "prior-auth-local",
        "name": "Prior Auth Local",
        "values": env_values,
    }

    (OUT / "Prior_Auth_API.postman_collection.json").write_text(
        json.dumps(collection, indent=2) + "\n"
    )
    (OUT / "Prior_Auth_API.postman_environment.json").write_text(
        json.dumps(environment, indent=2) + "\n"
    )

    submit = next(
        i
        for i in items
        if i["request"]["method"] == "POST" and i["request"]["url"]["path"] == ["v1", "prior-auths"]
    )
    assert "J06.9" in submit["request"]["body"]["raw"], submit["request"]["body"]["raw"]
    assert "{{member_id}}" in submit["request"]["body"]["raw"]
    decide = next(i for i in items if "/decision" in i["request"]["url"]["raw"])
    assert "{{procedure_id}}" in decide["request"]["body"]["raw"]
    reassign = next(i for i in items if "/reassign" in i["request"]["url"]["raw"])
    assert "{{reviewer_id}}" in reassign["request"]["body"]["raw"]
    claim = next(i for i in items if i["request"]["url"]["raw"].endswith("/claim"))
    assert claim["request"]["auth"]["bearer"][0]["value"] == "{{reviewer_token}}"

    paths = {item["request"]["url"]["raw"] for item in items}
    required = [
        "{{base_url}}/v1/prior-auths",
        "{{base_url}}/v1/prior-auths/{{request_id}}/claim",
        "{{base_url}}/v1/prior-auths/{{request_id}}/decision",
        "{{base_url}}/v1/me/prior-auths",
        "{{base_url}}/v1/support/intake-rejections/{{correlation_id}}",
    ]
    for req in required:
        assert any(req == p or req in p for p in paths), (req, paths)
    print(f"Wrote {len(items)} requests to {OUT}")


if __name__ == "__main__":
    main()
