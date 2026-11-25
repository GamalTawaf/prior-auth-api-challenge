# Session handoff

## Active

All features feat-001…007 complete on `feat/prior-auth-api`.

## Walkthrough script (live)

1. Draw state machine from README Decisions
2. `docker compose up -d && uv run alembic upgrade head && uv run python scripts/seed.py`
3. `./scripts/demo.sh` — fail→support→submit→claim 409→COI→decide→member redaction
4. Show `tests/test_claim_concurrency.py` + claim SQL in `app/prior_auth/services/claim.py`
5. Show `tests/test_member_redaction.py` + `to_member_out`
6. Show audit GET + IntakeRejection support path
7. Optional stretch: auditor read-only audit route seam

## Blockers

None.

## Next

Coding/quality rules (dedup helpers+parametrize, call-style, ruff, FastAPI compile, gate summaries, 100% coverage) live in `AGENTS.md` + `.cursor/rules/coding-gates.mdc` + plan Testing strategy.

PR risk lanes (`low` / `medium` / `high` labels) live in `AGENTS.md` § Pull requests, `.cursor/rules/pr-lanes.mdc`, and `.github/PULL_REQUEST_TEMPLATE.md`. Agents must label every PR.

When ready to submit: private GitHub from template, push, add collaborator `rgavrilov5`.
