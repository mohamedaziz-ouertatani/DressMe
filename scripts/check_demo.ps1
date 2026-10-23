# Read-only check that the demo setup is up. Run it before the demo:
#     powershell -ExecutionPolicy Bypass -File scripts\check_demo.ps1
# It checks: the three containers (mongo, backend, frontend) are running and healthy,
# the backend answers /health, the frontend page answers, and Ollama answers (only a
# warning: the chat needs it, the rest of the app does not). It changes nothing.
# Exit code: 0 = all required checks passed, 1 = at least one failed.

param(
    [string]$Project = "dressme",           # docker compose project (the folder name)
    [string]$Backend = "http://localhost:8000",
    [string]$Frontend = "http://localhost:5173",
    [string]$Ollama = "http://127.0.0.1:11434"
)

$results = New-Object System.Collections.ArrayList
function Add-Result($status, $name, $detail) {
    [void]$results.Add([pscustomobject]@{ Status = $status; Check = $name; Detail = $detail })
}

# --- 1. containers ---------------------------------------------------------------------
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Add-Result "FAIL" "Docker" "Docker is not running: start Docker Desktop"
} else {
    foreach ($service in "mongo", "backend", "frontend") {
        $name = "$Project-$service-1"
        # state | health ("none" = the service has no health check, e.g. the frontend)
        $info = docker inspect -f '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' $name 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $info) {
            Add-Result "FAIL" "container $service" "$name not found: run 'docker compose up'"
            continue
        }
        $state, $health = $info.Trim() -split '\|'
        if ($state -ne "running") {
            Add-Result "FAIL" "container $service" "$name is $state"
        } elseif ($health -eq "none" -or $health -eq "healthy") {
            Add-Result "PASS" "container $service" "running, health: $health"
        } else {
            Add-Result "FAIL" "container $service" "running but $health (the backend needs ~1 min to load the models)"
        }
    }
}

# --- 2. HTTP answers ---------------------------------------------------------------------
function Test-Http($url, $mustContain) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
        if ($mustContain -and $r.Content -notmatch $mustContain) {
            return @{ Ok = $false; Detail = "HTTP $($r.StatusCode) but the answer is not what we expect" }
        }
        return @{ Ok = $true; Detail = "HTTP $($r.StatusCode)" }
    } catch {
        return @{ Ok = $false; Detail = "no answer ($($_.Exception.Message))" }
    }
}

$r = Test-Http "$Backend/health" '"status"\s*:\s*"ok"'
Add-Result $(if ($r.Ok) { "PASS" } else { "FAIL" }) "backend /health" "$Backend/health: $($r.Detail)"

$r = Test-Http $Frontend $null
Add-Result $(if ($r.Ok) { "PASS" } else { "FAIL" }) "frontend page" "${Frontend}: $($r.Detail)"

# Ollama is the chat model's server: its absence only turns the chat off
$r = Test-Http $Ollama $null
Add-Result $(if ($r.Ok) { "PASS" } else { "WARN" }) "Ollama (chat model)" "${Ollama}: $($r.Detail)$(if (-not $r.Ok) { ' - the chat will not work; start Ollama (tray icon)' })"

# --- 3. summary ----------------------------------------------------------------------------
Write-Host ""
foreach ($x in $results) {
    $color = switch ($x.Status) { "PASS" { "Green" } "WARN" { "Yellow" } default { "Red" } }
    Write-Host ("[{0}] {1,-22} {2}" -f $x.Status, $x.Check, $x.Detail) -ForegroundColor $color
}
$failed = @($results | Where-Object { $_.Status -eq "FAIL" }).Count
$warned = @($results | Where-Object { $_.Status -eq "WARN" }).Count
Write-Host ""
if ($failed -eq 0) {
    $extra = if ($warned) { " ($warned warning(s))" } else { "" }
    Write-Host "RESULT: PASS - the demo setup is up$extra" -ForegroundColor Green
    exit 0
}
Write-Host "RESULT: FAIL - $failed required check(s) failed" -ForegroundColor Red
exit 1
