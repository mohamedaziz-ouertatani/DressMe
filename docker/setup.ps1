# One-time setup of a PC for the Docker version of DressMe (README "Run with Docker").
# Run it from the project folder:
#     powershell -ExecutionPolicy Bypass -File docker\setup.ps1
# It creates backend\.env if it is missing (never overwrites it), registers the chat
# model in Ollama if needed, and lists the data / model files you still need.
# It never touches git, and running it again is safe.

# (no "Stop" error mode: in Windows PowerShell it turns the normal progress messages that
# docker / ollama print on stderr into errors; the checks below look at exit codes)
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# --- 1. Docker must be running ------------------------------------------------------
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker is not running: start Docker Desktop, then run this script again." -ForegroundColor Red
    exit 1
}

# --- 2. backend\.env: settings + a secret key, only if missing -----------------------
$envFile = Join-Path $root "backend\.env"
if (Test-Path $envFile) {
    Write-Host "backend\.env already exists: kept as it is"
} else {
    # 48 random bytes -> 64 URL-safe characters (the backend needs at least 32)
    $bytes = New-Object byte[] 48
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $secret = [Convert]::ToBase64String($bytes).Replace('+', '-').Replace('/', '_')
    $text = [IO.File]::ReadAllText((Join-Path $root "backend\.env.example"))
    $text = $text -replace '(?m)^JWT_SECRET=.*$', "JWT_SECRET=$secret"
    $text = $text -replace '(?m)^CHAT_ENGINE=.*$', 'CHAT_ENGINE=ollama'
    $text = $text -replace '(?m)^OLLAMA_MODEL=.*$', 'OLLAMA_MODEL=dressme-chat-v4'
    # UTF-8 without BOM (Windows PowerShell's Set-Content would add one)
    [IO.File]::WriteAllText($envFile, $text, (New-Object Text.UTF8Encoding($false)))
    Write-Host "created backend\.env (new secret key; chat = local dressme-chat-v4)"
}

# --- 3. The chat model in Ollama (runs on the PC, not in Docker) ---------------------
$model = "dressme-chat-v4"
$folder = Join-Path $root "models\llm\$model"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama is not installed: get it from https://ollama.com and run this script again (the chat needs it)." -ForegroundColor Yellow
} elseif ((ollama list | Out-String) -match "(?m)^$model(:latest)?\s") {
    Write-Host "$model already registered in Ollama"
} else {
    $gguf = Get-ChildItem (Join-Path $folder "gguf") -Filter *.gguf -ErrorAction SilentlyContinue | Select-Object -First 1
    $modelfile = Join-Path $folder "Modelfile"
    if (-not $gguf -or -not (Test-Path $modelfile)) {
        Write-Host "Chat model files missing (models\llm\$model\Modelfile + gguf\*.gguf): ask a teammate for them." -ForegroundColor Yellow
    } else {
        # the Modelfile may point to the folder of the PC it was made on: point it here
        $lines = [IO.File]::ReadAllLines($modelfile)
        $lines = $lines | ForEach-Object { if ($_ -match '^FROM ') { "FROM ./gguf/$($gguf.Name)" } else { $_ } }
        [IO.File]::WriteAllLines($modelfile, $lines, (New-Object Text.UTF8Encoding($false)))
        Push-Location $folder
        try { ollama create $model -f Modelfile } finally { Pop-Location }
        Write-Host "$model registered in Ollama"
    }
}

# --- 4. The files that come from a teammate (never in git) -------------------------
$files = @(
    @("models\checkpoints\classifier_best.pt", "required"),
    @("models\checkpoints\colour_model.joblib", "required"),
    @("data\processed\dressme.csv", "required"),
    @("data\processed\embeddings\fashionclip.npy", "required"),
    @("data\processed\embeddings\fashionclip_ids.csv", "required"),
    @("data\raw\MarylandPolyVore\Re-PolyVore", "optional: look-alike pictures + demo wardrobe"),
    @("data\raw\FashionProduct\images", "optional: look-alike pictures"),
    @("data\processed\hm.csv", "optional: H&M look-alikes"),
    @("data\processed\embeddings\hm_fashionclip.npy", "optional: H&M look-alikes"),
    @("data\processed\shop_demo.csv", "optional: shop snapshot")
)
Write-Host "`nFiles from a teammate:"
$missing = 0
foreach ($f in $files) {
    if (Test-Path (Join-Path $root $f[0])) {
        Write-Host ("  ok       {0}" -f $f[0])
    } else {
        Write-Host ("  MISSING  {0}  ({1})" -f $f[0], $f[1]) -ForegroundColor Yellow
        if ($f[1] -eq "required") { $missing++ }
    }
}

# --- 5. What to do next ---------------------------------------------------------------
Write-Host ""
if ($missing -gt 0) {
    Write-Host "$missing required file(s) missing: the backend cannot start without them." -ForegroundColor Red
} else {
    Write-Host "Ready. Next:"
    Write-Host "  docker compose up --build        (first time ~10-20 min; then: docker compose up)"
    Write-Host "  docker compose exec backend python -m app.seed_demo   (demo accounts, once)"
    Write-Host "  open http://localhost:5173"
}
