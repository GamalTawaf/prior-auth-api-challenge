# Progress

## 2026-11-24 — full plan implementation

- feat-001…007 marked done
- System verified: compose up, migrate, seed, demo.sh, pytest 40 passed @ 100% coverage, mutmut 535/535 killed
- Branch: `feat/prior-auth-api`

## 2026-11-24 — coding gates into AI harness

- Added durable rules: no test/app duplication (conftest helpers + parametrize / shared utils), call-style, ruff, FastAPI compile in gates/CI, visible step summaries, 100% coverage
- Written to `AGENTS.md` § Coding & quality gates, `.cursor/rules/coding-gates.mdc`, plan Testing strategy + Commit/CI gates

## 2026-11-25 — PR risk lanes in AI harness

- Every PR must be labeled `low` | `medium` | `high` (behavior impact)
- `AGENTS.md`, `.cursor/rules/pr-lanes.mdc`, `.github/PULL_REQUEST_TEMPLATE.md`, `scripts/ensure_pr_labels.sh`
