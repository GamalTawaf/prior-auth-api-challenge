#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BASE_URL="${BASE_URL:-http://localhost:8000}"
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://prior:prior@localhost:5432/prior_auth}"
export JWT_SECRET="${JWT_SECRET:-dev-only-change-me-32bytes-min!!}"

uv run python scripts/seed.py | tee /tmp/prior-auth-seed.out
eval "$(python3 - <<'PY'
from pathlib import Path
text = Path("/tmp/prior-auth-seed.out").read_text()
for line in text.splitlines():
    line = line.strip()
    for role in ("office", "reviewer_coi", "reviewer", "admin", "member"):
        prefix = f"{role}:"
        if line.startswith(prefix):
            token = line[len(prefix):].strip()
            print(f'export {role.upper()}_TOKEN={token!r}')
            break
PY
)"

echo "== health =="
curl -sf "$BASE_URL/v1/health"
echo

TODAY=$(uv run python -c 'from app.clock import get_today; print(get_today().isoformat())')
MEMBER_ID=22222222-2222-2222-2222-222222222222
UNLINKED=22222222-2222-2222-2222-222222222299

echo "== 1) submit fail (unlinked) =="
FAIL=$(curl -s -X POST "$BASE_URL/v1/prior-auths" \
  -H "Authorization: Bearer $OFFICE_TOKEN" -H "Content-Type: application/json" \
  -d "{\"member_id\":\"$UNLINKED\",\"diagnosis_icd10\":\"J06.9\",\"date_of_service\":\"$TODAY\",\"clinical_note\":\"n\",\"procedures\":[{\"code\":\"99213\",\"units\":1}]}")
echo "$FAIL"
CID=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['correlation_id'])" "$FAIL")

echo "== 2) support lookup =="
curl -sf -H "Authorization: Bearer $OFFICE_TOKEN" \
  "$BASE_URL/v1/support/intake-rejections/$CID"
echo

echo "== 3) submit ok =="
OK=$(curl -s -X POST "$BASE_URL/v1/prior-auths" \
  -H "Authorization: Bearer $OFFICE_TOKEN" -H "Content-Type: application/json" \
  -d "{\"member_id\":\"$MEMBER_ID\",\"diagnosis_icd10\":\"J06.9\",\"date_of_service\":\"$TODAY\",\"clinical_note\":\"SECRET\",\"procedures\":[{\"code\":\"99213\",\"units\":1}]}")
echo "$OK"
RID=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['id'])" "$OK")

echo "== 4) claim =="
CLAIM=$(curl -sf -X POST -H "Authorization: Bearer $REVIEWER_TOKEN" \
  "$BASE_URL/v1/prior-auths/$RID/claim")
echo "$CLAIM"
echo "(second claim should 409)"
curl -s -o /dev/null -w "second_claim=%{http_code}\n" -X POST \
  -H "Authorization: Bearer $REVIEWER_TOKEN" \
  "$BASE_URL/v1/prior-auths/$RID/claim" || true

echo "== 5) COI claim =="
OK2=$(curl -s -X POST "$BASE_URL/v1/prior-auths" \
  -H "Authorization: Bearer $OFFICE_TOKEN" -H "Content-Type: application/json" \
  -d "{\"member_id\":\"$MEMBER_ID\",\"diagnosis_icd10\":\"J06.9\",\"date_of_service\":\"$TODAY\",\"procedures\":[{\"code\":\"99214\",\"units\":1}]}")
RID2=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['id'])" "$OK2")
curl -s -o /dev/null -w "coi_claim=%{http_code}\n" -X POST \
  -H "Authorization: Bearer $REVIEWER_COI_TOKEN" \
  "$BASE_URL/v1/prior-auths/$RID2/claim"

echo "== 6) decide =="
PROC=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['procedures'][0]['id'])" "$CLAIM")
DECIDE=$(curl -sf -X POST -H "Authorization: Bearer $REVIEWER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"outcomes\":[{\"procedure_id\":\"$PROC\",\"decision\":\"denied\",\"denial_reason\":\"Not medically necessary\"}]}" \
  "$BASE_URL/v1/prior-auths/$RID/decision")
echo "$DECIDE"

echo "== 7) member redaction =="
MEM=$(curl -sf -H "Authorization: Bearer $MEMBER_TOKEN" \
  "$BASE_URL/v1/me/prior-auths/$RID")
echo "$MEM"
python3 -c "import json,sys; b=json.loads(sys.argv[1]); assert 'clinical_note' not in b; assert 'denial_reason' not in json.dumps(b); assert b['procedures'][0]['status']=='not_approved'; print('member redaction OK')" "$MEM"

echo "Demo complete."
