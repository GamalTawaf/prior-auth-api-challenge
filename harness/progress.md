# Progress

## Last Updated

2026-11-24

## Current Objective

feat-001 — Decisions + local skeleton

## Recommended Next Step

Implement feat-001 per plan Task 1; verify with Compose health curl; mark done with evidence.

## 2026-11-24 — Root cleanup

- Moved council → `docs/council/`, assessment → `docs/harness/`, plan → `docs/plans/`.
- Agent state → `harness/` (`feature_list.json`, `progress.md`, `session-handoff.md`).
- Root keeps `AGENTS.md`, `CLAUDE.md`, `init.sh` only (plus future runtime files).

## 2026-11-24 — App domain packages

- Plan `app/` split by domain: `shared`, `identity`, `master_data`, `prior_auth`, `intake`, `audit` (not technical-layer folders).

## 2026-11-24 — Plan: Postman generator + skill scan

- Confirmed no existing Postman generator under `~/projects`; added to plan Task 6 / feat-006.
- Noted helpful ECC/attendi skills (fastapi-patterns, api-design, postgres-patterns, docker-patterns, tdd-workflow, etc.) in the plan.

## 2026-11-24 — Testing strategy locked

- Outside-in HTTP user-flow tests; mock only DB responses and/or external calls; never mock app internals.
- Exception: claim race + DB CHECKs use real Postgres (persistence under test).

## 2026-11-24 — Version policy: latest stable

- Python 3.15.x + Postgres 19 + latest stable library releases (floors dated in plan). OTel instrumentations may be 0.xbY (upstream pairing with SDK 1.x).
- uv: split prod (`[project].dependencies`) vs dev (`[dependency-groups] dev`); Docker `--no-dev`.

## 2026-11-24 — Harness created

- Scaffolded agent harness from walkinglabs harness-creator; customized for this take-home.
- Application code not started; `harness/feature_list.json` all `not-started`.
