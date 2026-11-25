# Session handoff

## Active

**feat-009 done** on branch `agent/wishlist-009` (awaiting `grit done`). Next: **feat-010** auditor via grit `wishlist-010` **after** 009 merges (linear alembic head).

Wishlist stretch — multi-agent via **[grit](https://github.com/rtk-ai/grit)** (AST locks + `.grit/worktrees/<agent>/`).

Plan: `docs/plans/2026-11-25-wishlist-outbox-maildev.md` (§ Grit).  
Reindex: `./scripts/grit_reindex.sh`. Binary: `~/.local/bin/grit` (v0.4.0).

| Feature | Coordination | Lane | Agent id | Status |
|---------|--------------|------|----------|--------|
| feat-008 | plain worktree → merged to `main` | medium | wishlist-008 | done |
| feat-009 | `grit claim -a wishlist-009` on `decide_request` (+ outbox package) | medium | wishlist-009 | done (pending grit done) |
| feat-010 | `grit claim -a wishlist-010` on `UserRole` / audit — after 009 migration head | high | wishlist-010 | next |
| feat-011 | `grit claim -a wishlist-011` on submit path | high | wishlist-011 | pending |
| feat-012 | docs after code `grit done` | low | wishlist-012 | pending |

Prefer **one PR per feature** with the lane label above. Use `grit done -a <id>` (main must be clean).

## Walkthrough script (live) — current MVP + outbox

1. Draw state machine from README Decisions
2. `docker compose up -d && uv run alembic upgrade head && uv run python scripts/seed.py`
3. `./scripts/demo.sh` — fail→support→submit→claim 409→COI→decide→member redaction
4. Show `tests/test_claim_concurrency.py` + claim SQL in `app/prior_auth/services/claim.py`
5. Show `tests/test_member_redaction.py` + `to_member_out`
6. Show audit GET + IntakeRejection support path
7. `GET /v1/reviewers/workload` as admin
8. Decide → refresh MailDev UI `:1080` (worker polls outbox)

## After wishlist

Add: auditor token on audit; double-submit with Idempotency-Key.

## Blockers for feat-010

- Alembic head must stay linear: current head **`20261125_outbox`** (revises `20261125_initial`). Auditor enum migration must set `down_revision = "20261125_outbox"` after 009 is merged/`grit done`.
- Do not start 010 migration until 009 lands on main (or rebase onto 009 head).

## Next

Parent: verify commit on `agent/wishlist-009` → `grit done -a wishlist-009`. Then implement **feat-010** in `.grit/worktrees/wishlist-010/`.
