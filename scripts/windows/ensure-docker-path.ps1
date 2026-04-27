<#
.SYNOPSIS
  Ensures Docker CLI directories are on the *user* PATH (no admin required).

.DESCRIPTION
  Docker Desktop normally registers itself, but some shells (or Cursor)
  start before the installer finishes, or PATH is stale. This script:
  1) Adds known Docker Desktop bin folders to the user PATH if they exist
     and are not already listed.
  2) Refreshes $env:Path in the current session.

  If Docker Desktop is not installed yet, nothing is added — install it first
  (see README or run install-docker-desktop.ps1 as Administrator).

.EXAMPLE
  .\scripts\windows\ensure-docker-path.ps1
#>
$ErrorActionPreference = "Stop"

$candidates = @(
    (Join-Path $env:ProgramFiles "Docker\Docker\resources\bin"),
    (Join-Path $env:ProgramFiles "Docker\Docker\resources\cli-plugins")
)

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$segments = @()
if ($userPath) {
    $segments = $userPath.Split(";", [System.StringSplitOptions]::RemoveEmptyEntries)
}

$toAdd = @()
foreach ($dir in $candidates) {
    if (-not (Test-Path -LiteralPath $dir)) { continue }
    if ($segments -contains $dir) { continue }
    $toAdd += $dir
}

if ($toAdd.Count -gt 0) {
    $newUserPath = ($toAdd + $segments) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
    Write-Host "Added to user PATH:" -ForegroundColor Green
    $toAdd | ForEach-Object { Write-Host "  $_" }
}
else {
    Write-Host "No Docker bin paths added (already present or Docker Desktop not installed under Program Files)." -ForegroundColor Yellow
}

& "$PSScriptRoot\refresh-path.ps1"

if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host "`ndocker OK:" -ForegroundColor Green
    docker version --format '{{.Client.Version}}' 2>$null
    if ($LASTEXITCODE -ne 0) { docker version }
}
else {
    Write-Host "`n'docker' still not found in this session." -ForegroundColor Yellow
    Write-Host "Install Docker Desktop, then run this script again and/or open a new terminal."
}
