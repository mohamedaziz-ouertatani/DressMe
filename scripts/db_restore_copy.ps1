# Restore a backup into a COPY database named dressme_copy, never into dressme.
#     powershell -ExecutionPolicy Bypass -File scripts\db_restore_copy.ps1 backups\dressme-<timestamp>.archive.gz
# The archive's "dressme.*" collections are renamed to "dressme_copy.*" while they are
# restored (mongorestore --nsFrom / --nsTo), so the real database is not written to.
# An older dressme_copy is replaced (--drop only affects dressme_copy). At the end it prints
# the document count of every collection in both databases side by side.

param(
    [Parameter(Mandatory = $true)][string]$Archive,
    [string]$Container = "dressme-mongo-1"
)

# (no "Stop" error mode: see db_backup.ps1)
$Source = "dressme"
$Target = "dressme_copy"          # fixed on purpose: this script can only write to the copy
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path $Archive)) {
    Write-Host "Archive not found: $Archive" -ForegroundColor Red
    exit 1
}
$archivePath = (Resolve-Path $Archive).Path
docker inspect -f "{{.State.Running}}" $Container *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Container $Container is not running: start the app with 'docker compose up' first." -ForegroundColor Red
    exit 1
}

$tmp = "/tmp/restore-copy.archive.gz"
docker cp $archivePath "${Container}:$tmp" *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Could not copy the archive into the container." -ForegroundColor Red
    exit 1
}

Write-Host "Restoring $Archive into '$Target' (the '$Source' database is not touched) ..."
# single quotes: PowerShell must not read the $...$ of the namespace pattern as variables
docker exec $Container mongorestore --archive=$tmp --gzip --drop --nsInclude='dressme.*' --nsFrom='dressme.$collection$' --nsTo='dressme_copy.$collection$' *> $null
$restored = $LASTEXITCODE
docker exec $Container rm -f $tmp *> $null
if ($restored -ne 0) {
    Write-Host "mongorestore failed (exit code $restored)." -ForegroundColor Red
    exit 1
}

# document count per collection, both databases side by side
function Get-Counts($db) {
    $js = "JSON.stringify(Object.fromEntries(db.getCollectionNames().map(c => [c, db[c].countDocuments({})])))"
    $json = docker exec $Container mongosh $db --quiet --eval $js
    $counts = @{}
    ($json | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $counts[$_.Name] = $_.Value }
    return $counts
}
$real = Get-Counts $Source
$copy = Get-Counts $Target
$names = @($real.Keys) + @($copy.Keys) | Sort-Object -Unique

Write-Host ("`n{0,-18} {1,10} {2,14}   {3}" -f "collection", $Source, $Target, "same?")
$different = 0
foreach ($n in $names) {
    $a = if ($real.ContainsKey($n)) { $real[$n] } else { "-" }
    $b = if ($copy.ContainsKey($n)) { $copy[$n] } else { "-" }
    $same = ($a -eq $b)
    if (-not $same) { $different++ }
    Write-Host ("{0,-18} {1,10} {2,14}   {3}" -f $n, $a, $b, $(if ($same) { "yes" } else { "NO" }))
}
if ($different -eq 0) {
    Write-Host "`nThe copy has the same counts as '$Source'." -ForegroundColor Green
} else {
    Write-Host "`n$different collection(s) differ (normal if '$Source' changed after the backup)." -ForegroundColor Yellow
}
