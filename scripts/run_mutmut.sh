#!/usr/bin/env bash
# Mutation testing against a shared Postgres must be serial: each pytest session
# drops/recreates public schema, so parallel mutmut children race and fail stats
# (UndefinedTable / "failed to collect stats").
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Optional ceiling while driving survivors to zero. Unset or 0 = require none.
MAX_SURVIVORS="${MUTMUT_MAX_SURVIVORS:-0}"

# Default: wipe mutants/ so we do not print a stale 🎉/🙁 spinner at 0.00 mut/s.
# Set MUTMUT_KEEP_CACHE=1 to resume an interrupted run.
if [[ "${MUTMUT_KEEP_CACHE:-0}" != "1" ]]; then
  echo "=== clearing mutants/ cache (set MUTMUT_KEEP_CACHE=1 to keep) ==="
  rm -rf mutants
fi

echo "=== mutmut (max-children=1) ==="
uv run mutmut run --max-children 1 "$@"

results="$(uv run mutmut results 2>&1 || true)"
echo "$results"

# `mutmut results` lists survivors / not-checked only (killed mutants are omitted).
survived="$(printf '%s\n' "$results" | grep -c ': survived$' || true)"
unchecked="$(printf '%s\n' "$results" | grep -c ': not checked$' || true)"

echo "summary: survived=${survived} not_checked=${unchecked} max_survivors=${MAX_SURVIVORS}"

if [[ "${unchecked}" -gt 0 ]]; then
  echo "mutmut gate failed: ${unchecked} mutants not checked" >&2
  exit 1
fi

if [[ "${survived}" -gt "${MAX_SURVIVORS}" ]]; then
  echo "mutmut gate failed: ${survived} survivors > max ${MAX_SURVIVORS}" >&2
  exit 1
fi

echo "mutmut gate passed"
