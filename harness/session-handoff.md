# Session handoff

## Active

**feat-012 done** (wishlist docs + demo) on branch `agent/wishlist-012`. Await parent `grit done -a wishlist-012`.

Wishlist stretch (feat-008…012) complete. Plan: `docs/plans/2026-11-25-wishlist-outbox-maildev.md`.

| Feature | Status |
|---------|--------|
| feat-008 workload | done |
| feat-009 outbox→MailDev | done |
| feat-010 auditor | done |
| feat-011 Idempotency-Key | done |
| feat-012 docs + demo | done |

## Walkthrough (45-min)

1. State machine + invariants from README Decisions
2. `docker compose up -d && uv run alembic upgrade head && uv run python scripts/seed.py`
3. `./scripts/demo.sh` covers:
   - failed submit → support lookup
   - happy submit with **Idempotency-Key** → replay same id
   - claim + second claim **409**
   - **workload** (`GET /v1/reviewers/workload`)
   - COI claim **403**
   - decide → **MailDev** notice (UI `:1080` / `GET /email`)
   - **auditor** `GET …/audit`
   - member redaction (`clinical_note` / `denial_reason` stripped)
4. Defend: outbox vs SMTP-in-decide; MailDev as sink; Idempotency only on submit; auditor ≠ admin

## Blockers

None.

## Next

Parent merges via `grit done -a wishlist-012`. Epic complete unless further polish requested.
