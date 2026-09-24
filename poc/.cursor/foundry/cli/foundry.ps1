#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

$FoundryScript = Join-Path $PSScriptRoot 'foundry.py'
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    $PythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $PythonCmd) {
    Write-Error 'python or python3 was not found on PATH'
    exit 1
}

& $PythonCmd.Source $FoundryScript @args
exit $LASTEXITCODE
