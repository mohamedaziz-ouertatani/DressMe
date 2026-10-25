# One-time setup of a PC for the Docker version of DressMe (README "Run with Docker").
# Run it from the project folder:
#     powershell -ExecutionPolicy Bypass -File docker\setup.ps1
# It creates backend\.env if it is missing (never overwrites it) and lists the data / model
# files you still need.
# It never touches git, and running it again is safe.

# (no "Stop" error mode: in Windows PowerShell it turns the normal progress messages that
# docker prints on stderr into errors; the checks below look at exit codes)
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
    # UTF-8 without BOM (Windows PowerShell's Set-Content would add one)
    [IO.File]::WriteAllText($envFile, $text, (New-Object Text.UTF8Encoding($false)))
    Write-Host "created backend\.env (new secret key)"
}

# --- 3. The files that come from a teammate (never in git) -------------------------
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

# --- 4. What to do next ---------------------------------------------------------------
Write-Host ""
if ($missing -gt 0) {
    Write-Host "$missing required file(s) missing: the backend cannot start without them." -ForegroundColor Red
} else {
    Write-Host "Ready. Next:"
    Write-Host "  docker compose up --build        (first time ~10-20 min; then: docker compose up)"
    Write-Host "  docker compose exec backend python -m app.seed_demo   (demo accounts, once)"
    Write-Host "  open http://localhost:5173"
}
