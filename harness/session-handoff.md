# Session handoff

## Active

**feat-010 done** on `agent/wishlist-010` (awaiting parent `grit done`). Next: **feat-011** Idempotency-Key via grit `wishlist-011`.

Wishlist stretch — multi-agent via **[grit](https://github.com/rtk-ai/grit)** (AST locks + `.grit/worktrees/<agent>/`).

Plan: `docs/plans/2026-11-25-wishlist-outbox-maildev.md` (§ Grit).  
Reindex: `./scripts/grit_reindex.sh`. Binary: `~/.local/bin/grit` (v0.4.0).

| Feature | Coordination | Lane | Agent id | Status |
|---------|--------------|------|----------|--------|
| feat-008 | plain worktree → merged to `main` | medium | wishlist-008 | done |
| feat-009 | `grit claim` → `grit done` (outbox + MailDev) | medium | wishlist-009 | done |
| feat-010 | `grit claim -a wishlist-010` on `UserRole` / audit | high | wishlist-010 | done |
| feat-011 | `grit claim -a wishlist-011` on submit path | high | wishlist-011 | next |
| feat-012 | docs after code `grit done` | low | wishlist-012 | pending |

Prefer **one PR per feature** with the lane label above. Use `grit done -a <id>` (main must be clean).

## Walkthrough script (live) — current MVP + outbox + auditor

1. Draw state machine from README Decisions
2. `docker compose up -d && uv run alembic upgrade head && uv run python scripts/seed.py`
3. `./scripts/demo.sh` — fail→support→submit→claim 409→COI→decide→member redaction
4. Show `tests/test_claim_concurrency.py` + claim SQL in `app/prior_auth/services/claim.py`
5. Show `tests/test_member_redaction.py` + `to_member_out`
6. Show audit GET as **auditor** + IntakeRejection support path
7. `GET /v1/reviewers/workload` as admin
8. Decide → refresh MailDev UI `:1080` (worker polls outbox)

## After wishlist

Add: double-submit with Idempotency-Key (feat-011).

## Blockers for feat-011

- Alembic head after feat-010 merge: **`20261125_auditor`** — Idempotency-Key migration must set `down_revision = "20261125_auditor"`.

## Next

Implement **feat-011** in `.grit/worktrees/wishlist-011/` (after `grit done -a wishlist-010`) → verify `uv run pytest tests/test_idempotency.py -v`; `./scripts/gates.sh`; `grit done -a wishlist-011`.
