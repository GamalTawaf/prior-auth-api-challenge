# Session handoff

## Active

**feat-008 done.** Next: **feat-009** (Outbox + MailDev) on `feat/wishlist-009-outbox`.

Wishlist stretch — multi-agent, one git worktree per feature (stacked; alembic conflicts prevent true parallel).

Plan: `docs/plans/2026-11-25-wishlist-outbox-maildev.md`.

| Feature | Branch / worktree | Lane | Agent | Status |
|---------|-------------------|------|-------|--------|
| feat-008 | `feat/wishlist-008-workload` → `.worktrees/feat-008-workload` | medium | agent-008 | done |
| feat-009 | `feat/wishlist-009-outbox` → `.worktrees/feat-009-outbox` (from 008) | medium | agent-009 | next |
| feat-010 | `feat/wishlist-010-auditor` → `.worktrees/feat-010-auditor` (from 009) | high | agent-010 | pending |
| feat-011 | `feat/wishlist-011-idempotency` → `.worktrees/feat-011-idempotency` (from 010) | high | agent-011 | pending |
| feat-012 | `feat/wishlist-012-docs` → `.worktrees/feat-012-docs` (from 011) | low | agent-012 | pending |

Prefer **one PR per feature** with the lane label above.

## Walkthrough script (live) — current MVP

1. Draw state machine from README Decisions
2. `docker compose up -d && uv run alembic upgrade head && uv run python scripts/seed.py`
3. `./scripts/demo.sh` — fail→support→submit→claim 409→COI→decide→member redaction
4. Show `tests/test_claim_concurrency.py` + claim SQL in `app/prior_auth/services/claim.py`
5. Show `tests/test_member_redaction.py` + `to_member_out`
6. Show audit GET + IntakeRejection support path

## After wishlist

Add: decide → MailDev UI `:1080`; workload curl; auditor token on audit; double-submit with Idempotency-Key.

## Blockers

None.

## Next

Implement **feat-009** only → verify `uv run pytest tests/test_outbox.py -v` then Compose MailDev/worker; `./scripts/gates.sh`.
