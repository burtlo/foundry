# validate-sync-prd-caller.ps1
#
# Twin of validate-sync-prd-caller.sh. Intent: sync-prd-step.md (checklist).
# Run from an app repo root ({app_folder}). Exit 0 when .github/workflows/sync-prd.yml
# matches org caller requirements.
#
# Windows (PowerShell 5.1):
#   powershell -NoProfile -File "{org_repo_path}/.cursor/foundry/scripts/validate-sync-prd-caller.ps1"

$ErrorActionPreference = 'Continue'

$File = if ($env:SYNC_PRD_FILE) { $env:SYNC_PRD_FILE } else { '.github/workflows/sync-prd.yml' }
$script:errors = 0

function Fail([string]$msg) {
    [Console]::Error.WriteLine("FAIL: $msg")
    $script:errors++
}

function Ok([string]$msg) {
    Write-Output "OK: $msg"
}

if (-not (Test-Path -LiteralPath $File)) {
    Fail "$File does not exist - copy from github-private/.cursor/foundry/templates/sync-prd-caller.yml"
    [Console]::Error.WriteLine("validate-sync-prd-caller: failed ($($script:errors) checks)")
    exit 1
}

$content = Get-Content -LiteralPath $File -Raw
$lines = Get-Content -LiteralPath $File

$hasOn = $false
$hasWorkflowCall = $false
foreach ($line in $lines) {
    if ($line -match '^on:') { $hasOn = $true }
    if ($line -match 'workflow_call:') { $hasWorkflowCall = $true }
}
if ($hasOn -and $hasWorkflowCall) {
    Fail "$File looks like the org reusable workflow - run this script from an app repo caller at .github/workflows/sync-prd.yml"
    [Console]::Error.WriteLine("validate-sync-prd-caller: failed ($($script:errors) checks)")
    exit 1
}

$joined = $content
if ($joined -notmatch '(?m)^permissions:') {
    Fail "missing top-level permissions: (required for CodeQL and restrictive default GITHUB_TOKEN)"
}
if ($joined -notmatch 'contents:\s*read') {
    Fail "permissions must include contents: read"
}
if ($joined -notmatch 'ORG/factory/\.github/workflows/sync-prd\.yml@main') {
    Fail "must call ORG/factory/.github/workflows/sync-prd.yml@main"
}
if ($joined -notmatch 'O_GH_REPOSITORY_TOKEN') {
    Fail "must pass O_GH_REPOSITORY_TOKEN to the reusable workflow"
}
if ($joined -match 'O_AZURE_PRD_BLOB_CONNECTION_STRING|O_AZURE_SEARCH_ADMIN_KEY') {
    Fail "caller must NOT pass Azure blob/search secrets"
}

$permLine = 0
$jobsLine = 0
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($permLine -eq 0 -and $lines[$i] -match '^permissions:') { $permLine = $i + 1 }
    if ($jobsLine -eq 0 -and $lines[$i] -match '^jobs:') { $jobsLine = $i + 1 }
}
if ($permLine -eq 0 -or $jobsLine -eq 0 -or $permLine -ge $jobsLine) {
    Fail "permissions: block must appear immediately before jobs:"
}

if ($script:errors -gt 0) {
    [Console]::Error.WriteLine("validate-sync-prd-caller: $($script:errors) checks failed - fix with sync-prd-step.md (copy template, do not hand-write)")
    exit 1
}

Ok "$File caller is valid (permissions, org reusable workflow, token-only secrets)"
exit 0
