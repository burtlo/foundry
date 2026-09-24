param(
    [Parameter(Mandatory = $true)]
    [string]$Event
)

$ErrorActionPreference = "Stop"
$inputJson = [Console]::In.ReadToEnd()
if (-not $inputJson) { exit 0 }

try {
    $payload = $inputJson | ConvertFrom-Json
} catch {
    exit 0
}

$statePath = $env:FOUNDRY_STATE_PATH
if (-not $statePath) { exit 0 }

$runDir = Split-Path -Parent $statePath
$sessionPath = Join-Path $runDir "cursor-session.json"
$telemetryPath = Join-Path $runDir "cursor-telemetry.jsonl"

$conversationId = $payload.conversation_id
if ($conversationId) {
    if (-not (Test-Path $sessionPath)) {
        $session = @{
            schema_version = "1.0.0"
            conversation_id = $conversationId
            started_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        }
        $session | ConvertTo-Json -Depth 6 | Set-Content -Path $sessionPath -Encoding utf8
    }
}

$eventRecord = @{
    timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    hook_event = $Event
    conversation_id = $conversationId
    generation_id = $payload.generation_id
    model = $payload.model
    tool_name = $payload.tool_name
    duration_ms = $payload.duration
    message_count = $payload.message_count
    tool_call_count = $payload.tool_call_count
}
if ($Event -eq "stop") {
    if (Test-Path $sessionPath) {
        $session = Get-Content $sessionPath -Raw | ConvertFrom-Json
        $session | Add-Member -NotePropertyName completed_at -NotePropertyValue $eventRecord.timestamp -Force
        $session | ConvertTo-Json -Depth 6 | Set-Content -Path $sessionPath -Encoding utf8
    }
}

($eventRecord | ConvertTo-Json -Compress) + "`n" | Add-Content -Path $telemetryPath -Encoding utf8 -NoNewline
exit 0
