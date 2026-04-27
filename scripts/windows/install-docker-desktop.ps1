<#
.SYNOPSIS
  Installs Docker Desktop via winget (requires Administrator + UAC).

  Prefer a lighter setup? Use Docker Engine inside WSL only — see README
  section "Docker no WSL".

.EXAMPLE
  # Right-click PowerShell -> Run as Administrator, then:
  Set-Location D:\Rubethyst\granloader
  .\scripts\windows\install-docker-desktop.ps1
#>
$ErrorActionPreference = "Stop"

$principal = New-Object Security.Principal.WindowsPrincipal(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Run this script in an elevated PowerShell (Run as Administrator)."
}

winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements

Write-Host "`nAfter installation: start Docker Desktop once, finish WSL2 prompts if shown, then in a normal shell run:" -ForegroundColor Cyan
Write-Host "  .\scripts\windows\ensure-docker-path.ps1" -ForegroundColor White
Write-Host "  cd <repo>; docker compose up -d" -ForegroundColor White
