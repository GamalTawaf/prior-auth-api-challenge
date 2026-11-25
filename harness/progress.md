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

## 2026-11-25 — wishlist stretch planned (D + MailDev)

- Scope: workload, outbox→MailDev, auditor role, Idempotency-Key on submit, docs/demo
- Plan: `docs/plans/2026-11-25-wishlist-outbox-maildev.md`
- Harness: feat-008…012 `pending`; next = feat-008 workload (medium lane)
- Docs updated: `AGENTS.md`, `README.md` Decisions, MVP plan cross-links, session-handoff worktree table
- Execution: one Task agent + git worktree per feature, stacked (008→009→010→011→012)

## 2026-11-25 — feat-008 Reviewer workload API

- `GET /v1/reviewers/workload` (ops_admin): LEFT JOIN all `role=reviewer` with `open_count` of `in_review` claims
- Route on `app/prior_auth/router.py` + `ReviewerWorkloadOut`; tests in `tests/test_workload.py`
- Verify: `uv run pytest tests/test_workload.py -v`; `./scripts/gates.sh`
- Next: feat-009 outbox + MailDev
