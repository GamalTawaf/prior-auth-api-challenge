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

When ready to submit: private GitHub from template, push, add collaborator `rgavrilov5`.
