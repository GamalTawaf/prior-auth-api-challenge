# AGENTS.md

Prior Authorization API take-home (Oxbridge Health). Durable Python + PostgreSQL backend a teammate inherits; defendable in a 45-minute walkthrough.

## Startup Workflow

Before writing code:

1. Confirm working directory with `pwd` (repo root)
2. Read this file completely
3. Read `docs/plans/2026-11-24-prior-auth-api.md` (source of truth for scope)
4. Read `CLAUDE.md` (Karpathy behavioral rules)
5. Run `./init.sh` to verify environment health
6. Read `harness/feature_list.json` for current feature state
7. Review `harness/progress.md` and `harness/session-handoff.md` if resuming
8. Review recent commits with `git log --oneline -5` (after git init)

If baseline verification is failing, repair that first before adding new scope.

## Working Rules

- **One feature at a time**: Pick exactly one unfinished feature from `harness/feature_list.json` whose dependencies are `done`
- **Ponytail full**: YAGNI, fewest files, no speculative abstractions; never cut audit/RBAC/validation or plan-required tooling (uv, OTel, multi-stage Docker, mutmut, CI)
- **Versions**: Python 3.15 + Postgres 19 + latest stable PyPI deps (no alphas/RCs; OTel instrumentations may be upstream `0.xbY`); see plan Version policy
- **uv prod vs dev**: `[project].dependencies` = runtime; `[dependency-groups] dev` = pytest/httpx2/mutmut/ruff. `uv add` vs `uv add --dev`. Local/CI `uv sync`; Docker `uv sync --frozen --no-dev`
- **Karpathy**: think before coding; simplicity first; surgical diffs; every step has a verify check
- **No noise comments**: code must be clear from names/types; comment only when *why* is invisible
- **Verification required**: do not claim done without running the feature's verification (and `./init.sh` when the project has `pyproject.toml`)
- **Evidence required**: record commands + outcome in `harness/feature_list.json` `evidence` and append `harness/progress.md`
- **Tests = user flow**: send real HTTP API calls; mock **only** DB responses and/or external calls; never mock routers/services/schemas/RBAC. Claim race + DB CHECKs use real Postgres (persistence is under test).
- **Stay in scope**: do not implement wishlist (outbox, Idempotency-Key, notify, workload) unless a feature explicitly says so
- **Leave clean state**: next session must be able to run `./init.sh` immediately

## Coding & quality gates (always)

Also mirrored in `.cursor/rules/coding-gates.mdc`.

### No duplication

- **Tests:** do not copy-paste HTTP/setup. Reuse or extend `tests/conftest.py` helpers (`submit_ok`, `submit_and_claim`, `claim_as`, `decide_as`, `reassign_as`, `assert_has_error_code`, `role_headers`, race helpers, …). Prefer `@pytest.mark.parametrize` for same shape / different inputs. **Add a helper when a sequence appears twice.**
- **App:** when the same logic appears in 2+ places, extract a util (e.g. `app/prior_auth/services/common.py`: `has_coi`, `get_request`, `audit_commit_refresh`; `raise_validation` / `raise_field` in `app/shared/errors.py`). No speculative layers for one call site.

### Call style (`scripts/check_call_style.py`)

- No `IfExp` / `and`/`or` BoolOp / `Lambda` inside function-call **arguments** (`app/` + `tests/`).
- No nested non-constructor Calls inside call arguments (`app/` only; `**/models.py` and `**/schemas.py` exempt). CapWords constructors OK.
- Extract locals before the call; do not “fix” by nesting.

### Lint, compile, coverage, summaries

- **ruff** `format --check` + `check` on `app` `tests` `scripts`.
- **FastAPI compile** (`scripts/check_fastapi_compile.py`) — import `app.main:app` + OpenAPI sanity — required in commit gates and CI.
- **pytest** with **100%** line + branch coverage (`fail_under = 100`).
- Claim done only after `./scripts/gates.sh` (or equivalent) is green.
- **Every** gates/CI step must print a visible summary (`### title` + body; write to `$GITHUB_STEP_SUMMARY` in Actions). New steps must follow `scripts/gates.sh` `run_step` / CI `| tee` + summary pattern — no silent steps.

## Layout

```
.                         # entrypoints + runtime project files only
├── AGENTS.md / CLAUDE.md / init.sh
├── harness/              # agent state
├── docs/{plans,council,harness}/
├── app/                  # domain packages (feat-001+)
│   ├── shared/           # errors, deps
│   ├── identity/         # users, JWT, RBAC
│   ├── master_data/      # practices, members, coverage, COI
│   ├── prior_auth/       # submit/claim/decide/reassign + routers
│   ├── intake/           # IntakeRejection + support lookup
│   └── audit/            # AuditEvent + writer + audit router
├── tests/ / scripts/ / postman/
```

## Required Artifacts

- `harness/feature_list.json` — feature state (source of truth for what to build next)
- `harness/progress.md` — session continuity log
- `init.sh` — startup and verification
- `harness/session-handoff.md` — multi-session handoff
- `docs/plans/2026-11-24-prior-auth-api.md` — full plan
- `CLAUDE.md` — Karpathy guidelines

## Definition of Done

A feature is done only when ALL of the following are true:

- [ ] Target behavior is implemented
- [ ] Required verification actually ran
- [ ] Evidence recorded in `harness/feature_list.json` and `harness/progress.md`
- [ ] Repository remains restartable from `./init.sh`
- [ ] No unrelated files changed

## End of Session

1. Update `harness/progress.md` with current state
2. Update `harness/feature_list.json` status + evidence
3. Update `harness/session-handoff.md` (active feature, blockers, next step)
4. Record unresolved risks
5. Commit when work is in a safe state (if user asked for commits)
6. Leave repo clean enough for next session to run `./init.sh`

## Verification Commands

```bash
./init.sh
./scripts/gates.sh
```

When `pyproject.toml` exists, init installs the git pre-commit hook and runs:

- `uv sync` (prod + `dependency-groups.dev`)
- `./scripts/gates.sh` — ruff format/check, call-style, fastapi OpenAPI compile, pytest+coverage
- `docker build -t prior-auth-api:local .` (no push)

Pre-commit (after `./scripts/install_git_hooks.sh`): same gates with `GATES_SKIP_TESTS=1` (pytest still runs in CI/`./init.sh`).

Mutmut is a CI / feat-006 gate, not every local init (too slow). Always `./scripts/run_mutmut.sh` (creates `prior_auth_mutmut_{i}` DBs and runs with `MUTMUT_MAX_CHILDREN`, default 4; each pytest session claims a slot so schema drops do not race).

CI path filter: meta-only diffs (docs/gitignore/etc.) no-op lint/test/mutate/image so required checks still pass; code-path changes run the full suite. Never rely on `[skip ci]`.

Postman (feat-006): `uv run python scripts/generate_postman_collection.py` writes local `postman/*.json` from OpenAPI (gitignored) with seed demo bodies + per-route role tokens — do not hand-edit or commit them.

## Pull requests — risk lanes (required)

Every PR must carry **exactly one** GitHub label: `low`, `medium`, or `high`. Mirrored in `.cursor/rules/pr-lanes.mdc` and `.github/PULL_REQUEST_TEMPLATE.md`.

| Lane | Label | Examples |
|------|-------|----------|
| **Low** | `low` | Docs/harness/`*.md`, comments, format-only, tooling config with no runtime behavior change |
| **Medium** | `medium` | Additive, backward-compatible API/schema (new response field, optional request field, new non-breaking route) |
| **High** | `high` | Logic/behavior of main components: validation, claim/decide/COI/RBAC, auth, semantic migrations, removed/renamed fields, status/`error_code` changes |

**Rules for agents opening a PR:**

1. Classify from the **full** diff; mixed changes → use the **highest** lane.
2. Run `./scripts/ensure_pr_labels.sh` once if labels may be missing.
3. Create/update the PR with `--label low|medium|high` and state `Lane: …` in the Summary.
4. Unsure whether behavior changed → treat as **high**.

## Escalation

- Architecture / compliance ambiguity → ask user (do not invent policy)
- Unclear requirements → re-read plan Decisions matrices; then ask
- Repeated test failures → update progress, stop expanding scope
- Scope ambiguity → re-read active feature in `harness/feature_list.json`
