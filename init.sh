#!/bin/bash
set -euo pipefail

echo "=== Harness Initialization ==="
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=== Harness files present ==="
test -f AGENTS.md
test -f CLAUDE.md
test -f harness/feature_list.json
test -f harness/progress.md
test -f harness/session-handoff.md
test -f docs/plans/2026-11-24-prior-auth-api.md

if [[ ! -f pyproject.toml ]]; then
  echo "=== Skeleton not created yet (no pyproject.toml) ==="
  echo "Active work: feat-001 Decisions + local skeleton"
  echo "Plan: docs/plans/2026-11-24-prior-auth-api.md"
  echo "State: harness/feature_list.json"
  echo "=== Pre-code harness OK ==="
  echo ""
  echo "Next steps:"
  echo "1. Read harness/feature_list.json — pick feat-001"
  echo "2. Implement only that feature"
  echo "3. Re-run ./init.sh after pyproject.toml exists"
  exit 0
fi

echo "=== uv sync (prod + dependency-groups.dev) ==="
uv sync

if [[ -d app ]]; then
  echo "=== uv run ruff check app tests ==="
  if [[ -d tests ]]; then
    uv run ruff check app tests
  else
    uv run ruff check app
  fi
fi

echo "=== uv run pytest -q ==="
set +e
uv run pytest -q
pytest_status=$?
set -e
# pytest exit 5 = no tests collected (OK early)
if [[ "$pytest_status" -ne 0 && "$pytest_status" -ne 5 ]]; then
  exit "$pytest_status"
fi

if [[ -f Dockerfile ]]; then
  echo "=== docker build -t prior-auth-api:local . (no push) ==="
  docker build -t prior-auth-api:local .
fi

echo "=== Verification Complete ==="
echo ""
echo "Next steps:"
echo "1. Read harness/feature_list.json to see current feature state"
echo "2. Pick ONE unfinished feature whose dependencies are done"
echo "3. Implement only that feature"
echo "4. Re-run ./init.sh before claiming done"
