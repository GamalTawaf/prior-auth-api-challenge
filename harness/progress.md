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
- Harness: feat-008…012; next after 008 = feat-009
- Docs updated: `AGENTS.md`, `README.md` Decisions, MVP plan cross-links, session-handoff
- Execution: one Task agent per feature; **grit** for parallel claim/merge (`https://github.com/rtk-ai/grit`); `scripts/grit_reindex.sh`; feat-008 used plain `.worktrees/` — 009+ use grit
- grit 0.4.0 at `~/.local/bin`; `./scripts/grit_reindex.sh` parks `.worktrees`/`.venv`

## 2026-11-25 — feat-008 Reviewer workload API

- `GET /v1/reviewers/workload` (ops_admin): LEFT JOIN all `role=reviewer` with `open_count` of `in_review` claims
- Route on `app/prior_auth/router.py` + `ReviewerWorkloadOut`; tests in `tests/test_workload.py`
- Verify: `uv run pytest tests/test_workload.py -v`; `./scripts/gates.sh`
- Merged to local `main` (`9e20abe`); next: feat-009 via grit `wishlist-009`

## 2026-11-25 — feat-009 Outbox + MailDev decision notify

- Migration `20261125_outbox`: `practices.notification_email` NOT NULL + `outbox_events`
- `app/outbox/`: models, mailer (stdlib smtplib), services enqueue/claim/process, worker module
- `decide_request` enqueues in same txn as audit; email body omits clinical_note / denial_reason
- Compose: `maildev` (1025/1080) + `outbox-worker` (`python -m app.outbox.worker`)
- Verify: `uv run pytest tests/test_outbox.py -v` → 12 passed; `./scripts/gates.sh`
- `grit done -a wishlist-009` → merge commit `b46534a` on local `main`
- Next: feat-010 auditor (alembic head = `20261125_outbox`)

## 2026-11-25 — feat-010 Auditor role

- `UserRole.auditor`; migration `20261125_auditor` (`down_revision = 20261125_outbox`) ADD VALUE via autocommit
- Seed `auditor@example.com` + Postman `auditor_token`; `AdminOrAuditor` on audit GET
- Read-all list/get via `OfficeAdminOrAuditor` / get_prior_auth auditor branch; mutations + workload + /me → 403
- Verify: `uv run pytest tests/test_auditor.py -v`; `./scripts/gates.sh`
- Next: feat-011 Idempotency-Key (alembic head = `20261125_auditor`)

