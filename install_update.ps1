param([Parameter(Mandatory=$true)][string]$ProjectRoot)
$ErrorActionPreference = 'Stop'
$sourceRoot = $PSScriptRoot
$targetRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
if ($sourceRoot.TrimEnd('\') -eq $targetRoot.TrimEnd('\')) { throw 'Extract the update into a separate folder, then run this installer targeting your PRISM folder.' }
if (!(Test-Path (Join-Path $targetRoot 'engine.py')) -or !(Test-Path (Join-Path $targetRoot 'app.py'))) { throw 'Choose the PRISM root containing your existing engine.py and app.py.' }
$files = Get-Content -Raw -LiteralPath (Join-Path $sourceRoot 'update-files.json') | ConvertFrom-Json
$backupRoot = Join-Path $targetRoot ('backups\engine-update-' + (Get-Date -Format 'yyyyMMdd-HHmmssfff'))
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
$newFiles = @()
foreach ($relative in $files) {
    if ($relative.Contains('..') -or [System.IO.Path]::IsPathRooted($relative)) { throw 'Invalid update manifest path.' }
    $from = Join-Path $sourceRoot $relative
    $to = Join-Path $targetRoot $relative
    if (Test-Path -LiteralPath $to) {
        $backup = Join-Path $backupRoot $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backup) | Out-Null
        Copy-Item -LiteralPath $to -Destination $backup -Force
    } else { $newFiles += $relative }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $to) | Out-Null
    Copy-Item -LiteralPath $from -Destination $to -Force
}
$newFiles | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $backupRoot 'new-files.json')
Write-Host "Update installed. Previous files: $backupRoot"
Write-Host 'Existing data, annotation projects, settings, and databases were not replaced.'
Write-Host 'Restart PRISM servers to load the new code, then run prism_annotator\install.ps1 if the prism command needs refreshing.'
