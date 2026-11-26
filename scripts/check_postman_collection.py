#!/usr/bin/env -S uv run python
"""Fail if committed Postman JSON drifts from a fresh OpenAPI generate.

Normalizes JWTs and ISO dates so mint_token / get_today do not cause false
failures. Run: ./scripts/generate_postman_collection.py then commit when this fails.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POSTMAN = ROOT / "postman"
COLLECTION = "Prior_Auth_API.postman_collection.json"
ENVIRONMENT = "Prior_Auth_API.postman_environment.json"

_JWT = re.compile(r"^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, str):
        if _JWT.fullmatch(value):
            return "<jwt>"
        # date_of_service lives inside raw JSON body strings
        return _ISO_DATE.sub("<date>", value)
    return value


def _load_normalized(path: Path) -> Any:
    return _normalize(json.loads(path.read_text()))


def main() -> int:
    for name in (COLLECTION, ENVIRONMENT):
        path = POSTMAN / name
        if not path.is_file():
            print(f"missing {path} — run ./scripts/generate_postman_collection.py and commit")
            return 1

    # Import after path checks so missing files fail fast without app import cost.
    from scripts import generate_postman_collection as gen

    tmp = Path(tempfile.mkdtemp(prefix="postman-check-"))
    try:
        old_out = gen.OUT
        gen.OUT = tmp
        try:
            gen.main()
        finally:
            gen.OUT = old_out

        drifts: list[str] = []
        for name in (COLLECTION, ENVIRONMENT):
            committed = _load_normalized(POSTMAN / name)
            generated = _load_normalized(tmp / name)
            if committed != generated:
                drifts.append(name)

        if drifts:
            print("Postman artifacts out of date vs OpenAPI/generator:")
            for name in drifts:
                print(f"  - postman/{name}")
            print(
                "Fix: ./scripts/generate_postman_collection.py && git add postman/Prior_Auth_API*.json"
            )
            return 1

        print(f"postman check ok ({COLLECTION}, {ENVIRONMENT})")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
