# Prior Authorization API

Oxbridge Health take-home: a durable Python + PostgreSQL prior-authorization backend.

OpenAPI: [http://localhost:8000/docs](http://localhost:8000/docs) after the stack is up.  
Deeper reference (Postman walkthrough, CI, observability, design notes): [`README_FULL.md`](README_FULL.md).

---

## How to run it

Step-by-step local run:

1. **Prerequisites:** Docker, [uv](https://docs.astral.sh/uv/), Python **3.15.x** (this repo pins **3.15.2**).
2. **Install deps:**

   ```bash
   uv sync
   ```

3. **Start the stack** (Postgres, API, MailDev, outbox worker, Grafana LGTM). The API entrypoint runs `alembic upgrade head` on boot:

   ```bash
   docker compose up --build -d
   ```

4. **Wait until the API is healthy:**

   ```bash
   curl -sf localhost:8000/v1/health
   ```

5. **Seed synthetic users / members / coverage** (prints Bearer JWTs for each role):

   ```bash
   uv run python scripts/seed.py
   ```

   JWT secret must match Compose (`JWT_SECRET`, default `dev-only-change-me-32bytes-min!!`). Seed roles: `office`, `reviewer`, `reviewer_coi`, `admin`, `auditor`, `member`.

6. **Exercise the API** — pick one:
   - OpenAPI UI: [http://localhost:8000/docs](http://localhost:8000/docs)
   - Scripted walkthrough: `./scripts/demo.sh`
   - Postman: see [`README_FULL.md`](README_FULL.md#postman)

7. **Optional checks:**

   ```bash
   ./scripts/gates.sh          # ruff, call-style, FastAPI compile, Postman fresh, pytest (100% coverage)
   ./scripts/demo.sh           # fail → support → submit → claim → decide → MailDev → member redaction
   ```

   Note: `pytest` drops/recreates the public schema on `DATABASE_URL` — re-seed (or restart `api`) afterward.

MailDev (decision emails): [http://localhost:1080](http://localhost:1080) · Grafana LGTM: [http://localhost:3000](http://localhost:3000)

---

## Decisions and assumptions

The brief says to make a call when something is unclear or contradictory and write it down. Below is what we treated as ambiguous and what we decided.

### Unclear / contradictory in the requirements → what we decided

| In the brief | Ambiguity | Decision |
|--------------|-----------|----------|
| “Offices **can** attach a clinical note” | Required vs optional | **Optional** (`null` / omitted). Requiring it invents a UM rule they did not state. Cap 10k chars when present. |
| “More than 30 units … is **almost always** a typo” | Soft flag vs hard reject | **Hard 422** with a “likely typo” message. Fail closed for MVP clarity. Enforced at the API boundary only (`units >= 1` in DB). |
| “Nationwide, from Maine to Hawaii” + “already happened” / “more than a year out” | Which calendar is “today”? | DOS is a `date`. “Today” and the far bound use **`America/New_York`**. “More than a year out” = strictly after `today + 365` days. |
| CPT / HCPCS / ICD-10 | Codebook membership vs shape | **Format (regex) only.** Unknown-but-well-formed codes pass intake; clinical validity is the reviewer’s job. |
| “My submission didn’t go through” (Support) | Lookup key not specified | Failed submits persist as **`IntakeRejection`** (not in the review queue) and return a **`correlation_id`**. Support: `GET /v1/support/intake-rejections/{correlation_id}`. No free-text search. |
| “Team leads want … open counts” (wishlist) vs roles listed (no “team lead”) | Who is a team lead? | **`ops_admin`** owns `GET /v1/reviewers/workload`. No separate lead role. |
| “Once a reviewer picks one up, it’s theirs … or an admin hands it to someone else” | Can admin decide / override the decision? | Admin **reassigns** only. **Decide = claim holder only.** |
| “Members … whether each procedure was approved” + “reviewer reasoning … must never see” | How to show denials without reasons | Member APIs strip `clinical_note` and `denial_reason`; outcomes surface as approved / not approved. |
| “A request marked approved with no record of who approved it … cannot happen again” | App-only vs DB-enforced | `decided` requires `decided_by_user_id` (**DB CHECK**), plus audit in the **same transaction** as every state change. |
| “Auditors are next” | Ship now or wait? | Shipped a read-only **auditor** role (wishlist/stretch): audit + list/get; mutations **403**. |
| Wishlist: notify offices on decision | Sync email from API vs durable delivery | **Transactional outbox** on decide → `outbox-worker` → MailDev. API never opens SMTP. |
| Partners connect their own systems | How much partner kit? | Live OpenAPI + generated Postman collection/env. Optional `Idempotency-Key` on submit for partner retries (not required by the brief; scoped to submit only). |

### State machine (so the matrices stay defendable)

```
[intake validation]
   ├─ fail → IntakeRejection (durable; NOT in review queue)
   └─ ok  → PriorAuthRequest status=submitted, claimed_by=NULL
                │
                ▼ claim (atomic UPDATE … WHERE submitted AND unclaimed)
         status=in_review, claimed_by=<reviewer>
                │
                ├─ admin reassign → other reviewer (still in_review)
                └─ decide (all procedures, one shot) → status=decided  (TERMINAL)
```

COI: a reviewer with a treat-edge to the member cannot claim or decide. Unlinked member → only `member_not_linked` (no pile-on coverage errors).

### Cut list (not built)

GraphQL, event bus, microservices, real IdP, appeals, retro review, CRUD UIs, AWS deploy, real SES/SendGrid (MailDev only).

---

## How you used AI

### What I asked it to do

1. **Plan pressure-test** — LLM council (`docs/council/`) on the draft project plan: cut list, status model, claim race, README-as-async-grader.
2. **Written plans** — turn the council output into executable plans (`docs/plans/…`) for MVP then wishlist.
3. **Implement against the plans** — Cursor agents, outside-in HTTP tests first, surgical diffs; keep humans owning Decisions, cut list, and race/audit/redaction invariants.
4. **Harness / CI / partner kit** — agents drafted gates, Postman generator, Compose OTel wiring once the product slice was stable.

### Where it got things wrong

| AI output | What was wrong | What I changed |
|-----------|----------------|----------------|
| “Use latest Python 3.15 via uv” | uv was offering a **3.15 beta**; not defendable for a take-home pin | Pinned **Homebrew + `python:3.15.2-slim`** explicitly |
| “Use the official uv Docker image” | **No** suitable official image for that pin | Install uv onto `python:3.15.2-slim` in the Dockerfile |
| Default mutmut layout | mutmut 3 needs `source_paths=app/` with `only_mutate` on services; bare runs raced schema drops and replayed stale `mutants/` cache | Wrapper `./scripts/run_mutmut.sh` + per-child DBs; gate on survivors |
| Early plan noise (outbox stub, Idempotency-Key, layered “phases”) before the vertical slice | Council correctly flagged portfolio theater; shipping empty seams would fail the walkthrough | **Cut** until after core submit/claim/decide/audit worked; then shipped outbox + idempotency as **named wishlist** with real behavior |
| Agent tendency to over-comment / abstract early | Noise and speculative layers vs “write it the way you’d want to find it” | Ponytail/Karpathy rules: no restating comments, extract utils only at 2+ call sites, humans kept the matrices |

### What stayed human-owned

State machine + audit/visibility matrices, hard units>30 rationale, TZ choice, IntakeRejection vs queue, claim SQL race, member redaction contract, and the cut list. AI drafted; I rejected or rewrote anything that could not be defended in the 45-minute session.

---

Partner docs, Postman cases, CI, and design notes: [`README_FULL.md`](README_FULL.md).
