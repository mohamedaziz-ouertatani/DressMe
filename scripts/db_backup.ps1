# Back up the DressMe database to backups\dressme-<timestamp>.archive.gz (git-ignored).
# Run it from anywhere:
#     powershell -ExecutionPolicy Bypass -File scripts\db_backup.ps1
# It runs mongodump INSIDE the MongoDB container (docker compose up must be running),
# copies the archive out, and prints how many documents each collection had.
# It only reads the database; running it again is safe (a new file each time).
# To check a backup without touching the real data, restore it into a copy:
#     powershell -ExecutionPolicy Bypass -File scripts\db_restore_copy.ps1 backups\<file>

param(
    [string]$Container = "dressme-mongo-1",
    [string]$Database = "dressme"
)

# (no "Stop" error mode: in Windows PowerShell it turns the progress messages that docker /
# mongodump print on stderr into errors; the checks below look at exit codes)
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

docker inspect -f "{{.State.Running}}" $Container *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Container $Container is not running: start the app with 'docker compose up' first." -ForegroundColor Red
    exit 1
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$name = "$Database-$stamp.archive.gz"
$backups = Join-Path $root "backups"
New-Item -ItemType Directory -Force $backups | Out-Null
$target = Join-Path $backups $name

# 1. dump inside the container (one gzip archive file, only this database)
Write-Host "Dumping '$Database' in $Container ..."
docker exec $Container mongodump --archive=/tmp/$name --gzip --db $Database *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "mongodump failed (exit code $LASTEXITCODE)." -ForegroundColor Red
    exit 1
}

# 2. copy it out, then remove the temporary copy in the container
docker cp "${Container}:/tmp/$name" $target *> $null
$copied = $LASTEXITCODE
docker exec $Container rm -f /tmp/$name *> $null
if ($copied -ne 0 -or -not (Test-Path $target) -or (Get-Item $target).Length -eq 0) {
    Write-Host "Could not copy the archive out of the container." -ForegroundColor Red
    exit 1
}

$mb = [math]::Round((Get-Item $target).Length / 1MB, 3)
Write-Host "Backup written: backups\$name ($mb MB)" -ForegroundColor Green

# 3. what was in the database, for comparing with a restore later
Write-Host "`nDocuments per collection in '$Database' now:"
$js = "db.getCollectionNames().sort().forEach(c => print(c + ' ' + db[c].countDocuments({})))"
docker exec $Container mongosh $Database --quiet --eval $js
