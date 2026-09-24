#!/usr/bin/env bash
# validate-sync-prd-caller.sh
#
# Twin of validate-sync-prd-caller.ps1. Intent: sync-prd-step.md (checklist).
# Run from an app repo root ({app_folder}). Exit 0 when .github/workflows/sync-prd.yml
# matches org caller requirements. Used by deliver.gate gate, Step 7d,
# delivery pre-commit, and devops-builder pre_pr_review.
#
# Usage (from app repo root {app_folder}; resolve {org_repo_path} per WORKSPACE.md):
#   bash "{org_repo_path}/.cursor/foundry/scripts/validate-sync-prd-caller.sh"
#   (or export GITHUB_PRIVATE={org_repo_path})

set -euo pipefail

FILE="${SYNC_PRD_FILE:-.github/workflows/sync-prd.yml}"
errors=0

fail() {
  echo "FAIL: $1" >&2
  errors=$((errors + 1))
}

ok() {
  echo "OK: $1"
}

if [[ ! -f "$FILE" ]]; then
  fail "$FILE does not exist — copy from github-private/.cursor/foundry/templates/sync-prd-caller.yml"
  echo "validate-sync-prd-caller: failed ($errors check(s))" >&2
  exit 1
fi

if grep -q '^on:' "$FILE" && grep -q 'workflow_call:' "$FILE"; then
  fail "$FILE looks like the org reusable workflow — run this script from an app repo caller at .github/workflows/sync-prd.yml"
  echo "validate-sync-prd-caller: failed ($errors check(s))" >&2
  exit 1
fi

grep -q '^permissions:' "$FILE" || fail "missing top-level permissions: (required for CodeQL and restrictive default GITHUB_TOKEN)"
grep -q 'contents: read' "$FILE" || fail "permissions must include contents: read"
grep -q 'ORG/factory/.github/workflows/sync-prd.yml@main' "$FILE" \
  || fail "must call ORG/factory/.github/workflows/sync-prd.yml@main"
grep -q 'O_GH_REPOSITORY_TOKEN' "$FILE" || fail "must pass O_GH_REPOSITORY_TOKEN to the reusable workflow"

if grep -qE 'O_AZURE_PRD_BLOB_CONNECTION_STRING|O_AZURE_SEARCH_ADMIN_KEY' "$FILE"; then
  fail "caller must NOT pass Azure blob/search secrets"
fi

perm_line="$(grep -n '^permissions:' "$FILE" | head -1 | cut -d: -f1 || true)"
jobs_line="$(grep -n '^jobs:' "$FILE" | head -1 | cut -d: -f1 || true)"
if [[ -z "$perm_line" || -z "$jobs_line" || "$perm_line" -ge "$jobs_line" ]]; then
  fail "permissions: block must appear immediately before jobs:"
fi

if [[ "$errors" -gt 0 ]]; then
  echo "validate-sync-prd-caller: $errors check(s) failed — fix with sync-prd-step.md (copy template, do not hand-write)" >&2
  exit 1
fi

ok "$FILE caller is valid (permissions, org reusable workflow, token-only secrets)"
exit 0
