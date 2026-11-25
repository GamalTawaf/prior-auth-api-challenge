# Session handoff

## Active

**Wishlist stretch complete** (feat-008…012). Stacked PRs opened against `main` / previous feature branch.

| Feature | Lane | Branch |
|---------|------|--------|
| feat-008 workload | medium | `feat/wishlist-008-workload` |
| feat-009 outbox→MailDev | medium | `feat/wishlist-009-outbox` |
| feat-010 auditor | high | `feat/wishlist-010-auditor` |
| feat-011 Idempotency-Key | high | `feat/wishlist-011-idempotency` |
| feat-012 docs + demo | low | `feat/wishlist-012-docs` |

Plan: `docs/plans/2026-11-25-wishlist-outbox-maildev.md`. Grit: `~/.local/bin/grit` + `./scripts/grit_reindex.sh`.

## Walkthrough

1. State machine from README Decisions
2. `docker compose up -d && uv run alembic upgrade head && uv run python scripts/seed.py`
3. `./scripts/demo.sh` — fail→support→submit→idempotency replay→claim 409→workload→COI→decide→MailDev→auditor→member redaction
4. Claim race + redaction tests as needed

## Blockers

None.

## Next

- Merge stacked PRs in order 008→012
- Add collaborator `rgavrilov5` when submitting the challenge
- Optional: remove stale `.worktrees/feat-008-workload`
