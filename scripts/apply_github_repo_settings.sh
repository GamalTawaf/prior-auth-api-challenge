#!/usr/bin/env bash
# Apply .github/repo-settings.json to the GitHub remote.
# Intent:
#   - Squash-only when merging PRs into main (ruleset allowed_merge_methods)
#   - Rebase enabled at repo level so PR "Update with rebase" is available
#   - Merge commits disabled; always suggest updating out-of-date PR branches
# Requires: gh auth with admin on the repo. Branch protection needs a public repo or GitHub Pro.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SETTINGS="$ROOT/.github/repo-settings.json"
REPO="${GITHUB_REPOSITORY:-}"
TMPDIR_APPLY="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_APPLY"' EXIT

if [[ ! -f "$SETTINGS" ]]; then
  echo "missing $SETTINGS" >&2
  exit 1
fi

if [[ -z "$REPO" ]]; then
  REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
fi

echo "=== apply repo settings → $REPO ==="

python3 - "$SETTINGS" "$TMPDIR_APPLY" <<'PY'
import json
import sys
from pathlib import Path

settings = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2])
(out / "repository.json").write_text(json.dumps(settings["repository"]))
bp = settings["branch_protection"]
(out / "branch.txt").write_text(bp["branch"])
payload = {
    "required_status_checks": bp["required_status_checks"],
    "enforce_admins": bp["enforce_admins"],
    "required_pull_request_reviews": bp["required_pull_request_reviews"],
    "restrictions": bp["restrictions"],
    "allow_force_pushes": bp["allow_force_pushes"],
    "allow_deletions": bp["allow_deletions"],
    "required_linear_history": bp["required_linear_history"],
    "required_conversation_resolution": bp["required_conversation_resolution"],
}
(out / "protection.json").write_text(json.dumps(payload))
(out / "rulesets.json").write_text(json.dumps(settings.get("rulesets", [])))
PY

gh api -X PATCH "repos/$REPO" --input "$TMPDIR_APPLY/repository.json"

BP_BRANCH="$(cat "$TMPDIR_APPLY/branch.txt")"
gh api -X PUT "repos/$REPO/branches/$BP_BRANCH/protection" \
  --input "$TMPDIR_APPLY/protection.json"

python3 - "$TMPDIR_APPLY/rulesets.json" "$REPO" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

rulesets = json.loads(Path(sys.argv[1]).read_text())
repo = sys.argv[2]


def gh_json(*args: str):
    raw = subprocess.check_output(["gh", "api", *args], text=True)
    return json.loads(raw) if raw.strip() else None


existing = gh_json(f"repos/{repo}/rulesets") or []
by_name = {item["name"]: item["id"] for item in existing}

for desired in rulesets:
    name = desired["name"]
    body = {
        "name": name,
        "target": desired.get("target", "branch"),
        "enforcement": desired["enforcement"],
        "conditions": desired["conditions"],
        "rules": desired["rules"],
    }
    path = Path(sys.argv[1]).with_name(f"ruleset-{name.replace(' ', '_')}.json")
    path.write_text(json.dumps(body))
    if name in by_name:
        print(f"=== update ruleset {name!r} (id={by_name[name]}) ===")
        subprocess.check_call(
            ["gh", "api", "-X", "PUT", f"repos/{repo}/rulesets/{by_name[name]}", "--input", str(path)]
        )
    else:
        print(f"=== create ruleset {name!r} ===")
        subprocess.check_call(
            ["gh", "api", "-X", "POST", f"repos/{repo}/rulesets", "--input", str(path)]
        )
PY

echo "=== verify ==="
gh api "repos/$REPO" --jq '{allow_squash_merge,allow_merge_commit,allow_rebase_merge,allow_update_branch,delete_branch_on_merge}'
gh api "repos/$REPO/branches/$BP_BRANCH/protection" \
  --jq '{allow_deletions:.allow_deletions.enabled,allow_force_pushes:.allow_force_pushes.enabled,enforce_admins:.enforce_admins.enabled,contexts:.required_status_checks.contexts,strict:.required_status_checks.strict,required_linear_history:.required_linear_history.enabled}'
gh api "repos/$REPO/rulesets" --jq '[.[] | {id,name,enforcement}]'
gh api "repos/$REPO/rules/branches/$BP_BRANCH" --jq '[.[] | select(.type=="pull_request") | .parameters.allowed_merge_methods]'

echo "=== apply_github_repo_settings: PASSED ==="
