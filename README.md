# Prior Authorization API

Durable Python + PostgreSQL prior-auth backend (Oxbridge Health take-home). Domain packages, one `/v1` surface, audit in the same transaction as state changes, role-scoped response schemas.

## How to run

```bash
# Requires Python 3.15.x (Homebrew 3.15.2), Docker, uv
uv sync
docker compose up --build -d          # api entrypoint runs alembic upgrade head
uv run python scripts/seed.py         # prints JWT tokens (required once after empty DB)
curl -sf localhost:8000/v1/health
# pytest drops/recreates public schema on DATABASE_URL — re-seed (or restart api) after
uv run pytest -q --cov=app --cov-report=term-missing   # fail_under=100
./scripts/demo.sh
```

OpenAPI: [http://localhost:8000/docs](http://localhost:8000/docs)

## Seed tokens

`uv run python scripts/seed.py` prints Bearer JWTs for:

| Role key | Use |
|----------|-----|
| `office` | provider office (practice Riverside Clinic) |
| `reviewer` | clean reviewer |
| `reviewer_coi` | reviewer with COI on seeded member |
| `admin` | ops admin |
| `member` | member portal |

Stable IDs (for curls): practice `11111111-…1111`, member `22222222-…2222`, unlinked `22222222-…2299`.

JWT secret must match the API (`JWT_SECRET`, default `dev-only-change-me-32bytes-min!!` in Compose).

## Decisions

### State machine

```
[intake validation]
   ├─ fail (domain OR schema/type) → IntakeRejection (durable; NOT in review queue)
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
- `decided` ⇒ `decided_by_user_id NOT NULL` (DB CHECK `ck_decided_requires_actor`)
- Reviewer with COI edge to member cannot claim or decide
- Unlinked member → only `member_not_linked` (no coverage / other member-derived checks)
- Caps: ≤50 procedures/outcomes, clinical_note ≤10k chars, body ≤256 KiB (app + proxy)

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
| Audit trail | ❌ | — | ❌ | ✅ |
| IntakeRejection lookup | ❌ | own practice by correlation_id | ❌ | all |

### Glossary

- **PriorAuthRequest** — accepted submission that may enter the review queue
- **IntakeRejection** — durable failed submit; never in the queue
- **Claim** — exclusive assignment to one reviewer
- **COI** — reviewer treats that member; blocked from claim/decide
- **Final** — `decided`; appeals out of scope

### Units > 30

Hard validation error with a “likely typo” message. Fail closed rather than soft-warn.

### Timezone

DOS stored as `date`. “Today” evaluated in `America/New_York` via `app/clock.py`.

### JWT secret — accepted risk, not production-ready

`settings.jwt_secret` keeps a committed default (`dev-only-change-me-32bytes-min!!`) so the
take-home runs with one command and no secret handling. **This is a deliberate demo trade-off.**

The risk, stated plainly: that default is published here, in `docker-compose.yml`, and in
`scripts/demo.sh`, and `scripts/seed.py` pins `ADMIN_ID` to a fixed UUID. A deployment that
forgets to set `JWT_SECRET` therefore lets anyone who has read this repo mint a valid
`ops_admin` token and read every request, chart note, and audit event in the system. The
failure is silent — the app boots normally.

Before any real deployment: drop the default so `Settings` raises on a missing `JWT_SECRET`,
require ≥32 bytes from a secret manager, and rotate anything that ever ran with the demo value.

### Token lifetime

`mint_token` sets `exp` (24h default), and `get_current_user` decodes with
`options={"require": ["exp"]}`. A token without an expiry claim is rejected rather than
accepted forever, so every issued credential — including seed and demo tokens — ages out.

### Cut list (not built)

Outbox / notify-on-decision, Idempotency-Key, GraphQL, event bus, microservices, real IdP, appeals, retro review, CRUD UIs, AWS deploy, reviewer workload API, auditor role (seam only).

### Coding standards

Ponytail full + Karpathy guidelines + no restating comments. Domain packages win over “fewest files.” Plan-required tooling is never cut.

### Runtime versions

- Python **3.15.2** (Homebrew / `python:3.15.2-slim`)
- PostgreSQL **19** (`postgres:19`)
- **uv** only; prod deps in `[project].dependencies`, test/lint in `[dependency-groups] dev`

## Gates (commit + CI)

```bash
./scripts/gates.sh                 # ruff format/check, call-style, fastapi compile, pytest
./scripts/install_git_hooks.sh     # pre-commit runs gates with GATES_SKIP_TESTS=1
```

- **ruff** — `ruff format --check` + `ruff check` (E/W/F/I/UP/B/SIM/C4/RUF)
- **call-style** — no nested non-constructor calls and no `if`/`and`/`or`/lambda expressions inside function call arguments (`scripts/check_call_style.py`; nested-call rule applies to `app/` except models/schemas)
- **fastapi compile** — `compileall` + `app.openapi()` + route callable inventory (`scripts/check_fastapi_compile.py`)

Every CI step writes a pass/fail block to the GitHub Actions job summary.

## CI

GitHub Actions (`.github/workflows/ci.yml`):

1. **test** — Postgres 19 service, `uv sync`, ruff, alembic, pytest with **100% coverage** gate
2. **mutate** — mutmut on `app/prior_auth/services` (see threshold below)
3. **image** — `docker build` only (no registry login/push)

### Mutmut threshold

Scoped via `setup.cfg`: `source_paths=app/`, `only_mutate=app/prior_auth/services/*`.

**Do not run bare `uv run mutmut run`.** Use the wrapper — it prepares per-child DBs and sets the worker count:

1. **Parallel children** each claim an exclusive `prior_auth_mutmut_{i}` DB (via flock) so `DROP SCHEMA test_prior_auth` does not race. Default `--max-children 4` (`MUTMUT_MAX_CHILDREN`). Pytest still uses schema `test_prior_auth` only; app/dev data in `prior_auth` is never dropped.
2. **Stale `mutants/` cache** → `0 files mutated` and a spinner at `0.00 mutations/second` replaying old 🎉/🙁 counts. Wipe the cache (or use the wrapper).

```bash
./scripts/run_mutmut.sh
# more workers: MUTMUT_MAX_CHILDREN=8 ./scripts/run_mutmut.sh
# resumes only: MUTMUT_KEEP_CACHE=1 ./scripts/run_mutmut.sh
```

`setup.cfg` sets `on_dependency_change=rerun` so non-Python dep changes also invalidate results.

**Gate:** 0 not-checked; survivors ≤ `MUTMUT_MAX_SURVIVORS` (default 0 in CI and locally).

## Postman

```bash
./scripts/generate_postman_collection.py
# or: uv run python scripts/generate_postman_collection.py
```

Writes `postman/*.json` from `app.openapi()` (not committed). Import the collection + **Prior Auth Local** environment. Each request already has a role token, path vars, and a demo JSON body (seed `member_id` / ICD / CPT). After Submit, paste `id` → `request_id` and `procedures[0].id` → `procedure_id` in the env, then Claim / Decide.

## Live walkthrough

```bash
./scripts/demo.sh
```

Covers: failed submit → support lookup → happy submit → claim + 409 race → COI 403 → decide → member redaction.

## How AI was used

- Plan: LLM council + `docs/plans/2026-11-24-prior-auth-api.md` (domain packages, cut wishlist, IntakeRejection, OTel, mutmut, CI).
- Implementation: Cursor agent following the plan with executing-plans / TDD, ponytail full, Karpathy surgical diffs.
- Wrong turns fixed: uv had only Python 3.15 beta → Homebrew/Docker **3.15.2**; no `uv:python3.15` image → install uv binary onto `python:3.15.2-slim`; mutmut 3 needs full `app/` in `source_paths` with `only_mutate` on services.
- Tests are outside-in HTTP (except persistence-truth claim race + DB CHECK).

## Design notes

- Flat domain packages under `app/` (identity, master_data, prior_auth, intake, audit, shared)
- Thin routers; rules in `prior_auth/services/*`
- Role-specific response schemas (member strips note + denial reason)
- OpenTelemetry in `telemetry.py` (console default; OTLP when `OTEL_EXPORTER_OTLP_ENDPOINT` set)
