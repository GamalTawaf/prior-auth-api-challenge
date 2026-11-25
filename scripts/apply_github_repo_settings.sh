#!/usr/bin/env bash
# Apply .github/repo-settings.json to the GitHub remote (squash-only + main protection).
# Requires: gh auth with admin on the repo. Branch protection needs a public repo or GitHub Pro.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SETTINGS="$ROOT/.github/repo-settings.json"
REPO="${GITHUB_REPOSITORY:-}"

if [[ ! -f "$SETTINGS" ]]; then
  echo "missing $SETTINGS" >&2
  exit 1
fi

if [[ -z "$REPO" ]]; then
  REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
fi

echo "=== apply repo settings → $REPO ==="

gh api -X PATCH "repos/$REPO" --input <(
  python3 - "$SETTINGS" <<'PY'
import json, sys
print(json.dumps(json.load(open(sys.argv[1]))["repository"]))
PY
)

BP_BRANCH="$(
  python3 - "$SETTINGS" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["branch_protection"]["branch"])
PY
)"

gh api -X PUT "repos/$REPO/branches/$BP_BRANCH/protection" --input <(
  python3 - "$SETTINGS" <<'PY'
import json, sys
bp = json.load(open(sys.argv[1]))["branch_protection"]
print(json.dumps({
    "required_status_checks": bp["required_status_checks"],
    "enforce_admins": bp["enforce_admins"],
    "required_pull_request_reviews": bp["required_pull_request_reviews"],
    "restrictions": bp["restrictions"],
    "allow_force_pushes": bp["allow_force_pushes"],
    "allow_deletions": bp["allow_deletions"],
    "required_linear_history": bp["required_linear_history"],
    "required_conversation_resolution": bp["required_conversation_resolution"],
}))
PY
)

echo "=== verify ==="
gh api "repos/$REPO" --jq '{allow_squash_merge,allow_merge_commit,allow_rebase_merge,delete_branch_on_merge}'
gh api "repos/$REPO/branches/$BP_BRANCH/protection" \
  --jq '{allow_deletions:.allow_deletions.enabled,allow_force_pushes:.allow_force_pushes.enabled,enforce_admins:.enforce_admins.enabled,contexts:.required_status_checks.contexts,strict:.required_status_checks.strict}'

echo "=== apply_github_repo_settings: PASSED ==="
