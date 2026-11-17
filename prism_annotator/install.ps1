# One-time per-user installation. No administrator access required.
$ErrorActionPreference = 'Stop'
$workbenchDir = $PSScriptRoot
$pythonPath = Join-Path $workbenchDir '.venv\Scripts\python.exe'

Write-Host 'PRISM | Installing terminal launcher' -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $pythonPath)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv (Join-Path $workbenchDir '.venv')
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv (Join-Path $workbenchDir '.venv')
    } else {
        throw 'Install Python 3.11 or later, then rerun this setup.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'Creating the virtual environment failed.' }
}
& $pythonPath -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required. Remove only this workbench .venv and recreate it using Python 3.11+.' }
& $pythonPath -m pip install -r (Join-Path $workbenchDir 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. The prism command was not installed.' }

$launcherDir = Join-Path $env:LOCALAPPDATA 'PRISM\bin'
New-Item -ItemType Directory -Force -Path $launcherDir | Out-Null
# A .cmd wrapper is discoverable by PowerShell without changing its execution policy.
$launcher = "@echo off`r`n`"$pythonPath`" `"$(Join-Path $workbenchDir 'cli.py')`" %*`r`n"
[System.IO.File]::WriteAllText((Join-Path $launcherDir 'prism.cmd'), $launcher, [System.Text.Encoding]::Default)
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (($userPath -split ';') -notcontains $launcherDir) {
    $updatedPath = if ([string]::IsNullOrWhiteSpace($userPath)) { $launcherDir } else { $userPath.TrimEnd(';') + ';' + $launcherDir }
    [Environment]::SetEnvironmentVariable('Path', $updatedPath, 'User')
}
if (($env:Path -split ';') -notcontains $launcherDir) { $env:Path = $launcherDir + ';' + $env:Path }
Write-Host ''
Write-Host 'Installed. Type prism to open the menu.' -ForegroundColor Green
Write-Host 'If setup was run in a separate process, open a new PowerShell window first.'
Write-Host 'Keep this workbench folder in place. After moving it, rerun install.ps1.'
