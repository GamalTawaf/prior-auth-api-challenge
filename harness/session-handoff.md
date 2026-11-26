# Session handoff

## Active

**feat-011 done** on `agent/wishlist-011` (awaiting parent `grit done`). Next: **feat-012** README / demo / cut-list (docs only; grit optional).

Wishlist stretch — multi-agent via **[grit](https://github.com/rtk-ai/grit)** (AST locks + `.grit/worktrees/<agent>/`).

Plan: `docs/plans/2026-11-25-wishlist-outbox-maildev.md` (§ Grit).  
Reindex: `./scripts/grit_reindex.sh`. Binary: `~/.local/bin/grit` (v0.4.0).

| Feature | Coordination | Lane | Agent id | Status |
|---------|--------------|------|----------|--------|
| feat-008 | plain worktree → merged to `main` | medium | wishlist-008 | done |
| feat-009 | `grit claim` → `grit done` (outbox + MailDev) | medium | wishlist-009 | done |
| feat-010 | `grit claim -a wishlist-010` on `UserRole` / audit | high | wishlist-010 | done |
| feat-011 | `grit claim -a wishlist-011` on submit path | high | wishlist-011 | done |
| feat-012 | docs after code `grit done` | low | wishlist-012 | next |

Prefer **one PR per feature** with the lane label above. Use `grit done -a <id>` (main must be clean).

## Walkthrough script (live) — current MVP + wishlist code

1. Draw state machine from README Decisions
2. `docker compose up -d && uv run alembic upgrade head && uv run python scripts/seed.py`
3. `./scripts/demo.sh` — fail→support→submit→claim 409→COI→decide→member redaction
4. Show `tests/test_claim_concurrency.py` + claim SQL in `app/prior_auth/services/claim.py`
5. Show `tests/test_member_redaction.py` + `to_member_out`
6. Show audit GET as **auditor** + IntakeRejection support path
7. `GET /v1/reviewers/workload` as admin
8. Decide → refresh MailDev UI `:1080` (worker polls outbox)
9. Double-submit with `Idempotency-Key` → same body replays; different body 409

## Blockers for feat-012

- Prefer `grit done -a wishlist-011` first so docs land on merged code (MailDev, workload, auditor, Idempotency-Key all on main).
- Alembic head after 011: **`20261125_idempotency`**.

## Next

Implement **feat-012** (README cut-list cleanup, demo.sh walkthrough, session-handoff polish) → verify `./scripts/demo.sh`; `grit done` if claimed.
