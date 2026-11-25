# Prior Authorization API

Durable Python + PostgreSQL prior-auth backend (Oxbridge Health take-home). Domain packages, one `/v1` surface, audit in the same transaction as state changes, role-scoped response schemas.

## How to run

```bash
# Requires Python 3.15, Docker, uv
uv sync
docker compose up --build -d
uv run alembic upgrade head
uv run python scripts/seed.py
curl -sf localhost:8000/v1/health
uv run pytest -q
./scripts/demo.sh   # after feat-006
```

OpenAPI: [http://localhost:8000/docs](http://localhost:8000/docs)

## Decisions

### State machine

```
[intake validation]
   ├─ fail → IntakeRejection (durable; NOT in review queue)
   └─ ok  → PriorAuthRequest status=submitted, claimed_by=NULL
                │
                ▼ claim (atomic)
         status=in_review, claimed_by=<reviewer>, claimed_at=now
                │
                ├─ admin reassign → claimed_by=<other> (still in_review)
                └─ decide (all procedures in one shot)
                       status=decided, decided_by, decided_at
                       each procedure: approved | denied (+ reason if denied)
                       TERMINAL — no further mutations
```

**Invariants**

- Queue = `submitted` AND `claimed_by_user_id IS NULL`
- Claim: `UPDATE … WHERE id=:id AND status='submitted' AND claimed_by_user_id IS NULL`
- Decide = claim holder only (no admin override)
- `decided` ⇒ `decided_by_user_id NOT NULL` (DB CHECK)
- Reviewer with COI edge to member cannot claim or decide

### Audit matrix

| Action | Actor | Persist | Audit payload (min) |
|--------|-------|---------|---------------------|
| intake_reject | office | IntakeRejection + AuditEvent | correlation_id, fields[], practice_id |
| submit | office | request + procedures + AuditEvent | request_id, member_id, procedure codes |
| claim | reviewer | claim fields + AuditEvent | request_id, reviewer_id |
| reassign | ops_admin | claim fields + AuditEvent | request_id, from, to |
| decide | reviewer | procedure decisions + decided_* + AuditEvent | per-procedure outcomes |

Audit writes in the **same DB transaction** as the state change.

### Visibility matrix

| Field / capability | Member | Office (own practice) | Reviewer | Ops admin |
|--------------------|--------|----------------------|----------|-----------|
| List/get requests | own only | own practice | queue unclaimed + own claimed | all |
| clinical_note | ❌ | ✅ | ✅ | ✅ |
| denial_reason / reasoning | ❌ (approved \| not_approved only) | ✅ | ✅ | ✅ |
| Audit trail | ❌ | own practice optional | ❌ | ✅ |
| IntakeRejection lookup | ❌ | own practice by correlation_id | ❌ | all |

### Glossary

- **PriorAuthRequest** — accepted submission that may enter the review queue
- **IntakeRejection** — durable failed submit; never in the queue
- **Claim** — exclusive assignment to one reviewer
- **COI** — reviewer treats that member; blocked from claim/decide
- **Final** — `decided`; appeals out of scope

### Units > 30

Hard validation error with a “likely typo” message. Almost never legitimate in this domain; fail closed rather than soft-warn.

### Timezone

DOS stored as `date`. “Today” evaluated in `America/New_York` via `app/clock.py`.

### Cut list (not built)

Outbox / notify-on-decision, Idempotency-Key, GraphQL, event bus, microservices, real IdP, appeals, retro review, CRUD UIs, AWS deploy, reviewer workload API, auditor role (seam noted only).

### Coding standards

Ponytail full + Karpathy guidelines + no restating comments. Domain packages win over “fewest files.” Plan-required tooling (uv, OTel, multi-stage Docker, mutmut, CI, IntakeRejection, DB CHECKs) is never cut.

### Runtime versions

- Python **3.15.2** (Homebrew / `python:3.15.2-slim`)
- PostgreSQL **19** (`postgres:19`)
- Package manager: **uv** only; prod deps in `[project].dependencies`, test/lint in `[dependency-groups] dev`

## Seed tokens

Documented after `scripts/seed.py` (feat-002).

## CI

GitHub Actions: pytest (Postgres 19), mutmut on `app/prior_auth/services`, `docker build` with **no push**.

## Postman

```bash
uv run python scripts/generate_postman_collection.py
```

Import `postman/Prior_Auth_API.postman_collection.json` + `postman/Prior_Auth_API.postman_environment.json`.

## How AI was used

(Stub — finalized in feat-007.) Plan authored with LLM council; implementation via Cursor agent following `docs/plans/2026-11-24-prior-auth-api.md`, ponytail full, and TDD.

## Live walkthrough

See `scripts/demo.sh` (feat-006).
