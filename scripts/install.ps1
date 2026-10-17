<#
.SYNOPSIS
  Installs PYTHIA Studio on Windows (through WSL2, because PYTHIA compiles Python to C++ with a Linux toolchain).

.DESCRIPTION
  1. Makes sure WSL2 with an Ubuntu distro exists (runs `wsl --install -d Ubuntu` if not; a reboot may be needed, then run this again).
  2. Runs scripts/install.sh INSIDE that distro (venv in ~/.pythia-studio/venv, system packages via apt after you approve).
  3. Creates a Start-Menu and Desktop shortcut that starts the app window, plus `pythia-studio.cmd` on your PATH.

  Nothing else on Windows is modified. Uninstall: wsl -d Ubuntu -e ~/.pythia-studio/uninstall.sh, then delete the shortcuts.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\install.ps1
  powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -FromSource      # install from this checkout
#>
[CmdletBinding()]
param(
  [string]$Distro = "",               # WSL distro to use (default: Ubuntu, else your default distro)
  [switch]$FromSource,                # install from this checkout instead of GitHub
  [string]$Spec = "",                 # any pip requirement, passed to install.sh --spec
  [string]$WslPrefix = "",            # install prefix inside WSL (default ~/.pythia-studio)
  [string]$ShortcutRoot = "",         # where to put shortcuts/.cmd (default: real Start Menu, Desktop, %LOCALAPPDATA%\PythiaStudio)
  [switch]$NoShortcuts,
  [switch]$DryRun                     # print what would happen
)
$ErrorActionPreference = "Stop"
$RawUrl = "https://raw.githubusercontent.com/Vishalvivek2007/Pythia/main/scripts/install.sh"

function Say($m)  { Write-Host "[pythia-install] $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "[pythia-install] $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "[pythia-install] ERROR: $m" -ForegroundColor Red; exit 1 }

Write-Host @"

PYTHIA Studio installer for Windows
-----------------------------------
PYTHIA turns hot Python functions into verified C++. The C++ toolchain lives in Linux, so on Windows
the app runs inside WSL2 (Windows Subsystem for Linux) and opens its window in your normal Edge/Chrome.
This script will: check WSL2 + Ubuntu, install PYTHIA into it, and add a Start-Menu / Desktop shortcut.

"@

# ---- 1. WSL ---------------------------------------------------------------------------------------------------
if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { Die "wsl.exe not found. Windows 10 2004+ or Windows 11 is required." }

function Get-Distros {
  $old = [Console]::OutputEncoding
  try { [Console]::OutputEncoding = [System.Text.Encoding]::Unicode; $out = & wsl.exe -l -q 2>$null } finally { [Console]::OutputEncoding = $old }
  @($out | ForEach-Object { ($_ -replace "`0", "").Trim() } | Where-Object { $_ -and $_ -notmatch "^docker-desktop" })
}
$distros = @(Get-Distros)
if ($Distro -eq "") {
  if ($distros -contains "Ubuntu") { $Distro = "Ubuntu" }
  elseif ($distros.Count -gt 0) { $Distro = $distros[0] }
}
if ($Distro -eq "" -or $distros -notcontains $Distro) {
  $want = if ($Distro) { $Distro } else { "Ubuntu" }
  Warn "No '$want' distro found in WSL."
  if ($DryRun) { Say "[dry run] would run: wsl --install -d $want"; $Distro = $want }
  else {
    Say "Running: wsl --install -d $want   (Windows may ask for administrator permission and for a restart)"
    & wsl.exe --install -d $want
    Warn "WSL was just installed. If Windows asks for a restart, restart now, finish the Ubuntu first-run user setup, then run this installer again."
    exit 0
  }
}
Say "Using WSL distro: $Distro"

# ---- 2. run install.sh inside WSL ------------------------------------------------------------------------------
$extra = @()
if ($Spec -ne "") { $extra += @("--spec", "'$Spec'") }
if ($WslPrefix -ne "") { $extra += @("--prefix", $WslPrefix) }
$checkout = Split-Path -Parent $PSScriptRoot
if ($FromSource) {
  if (-not (Test-Path (Join-Path $checkout "pyproject.toml"))) { Die "-FromSource needs to run from a PYTHIA checkout (pyproject.toml not found next to scripts\)." }
  $wslSrc = (& wsl.exe -d $Distro -e wslpath -a $checkout).Trim()
  $cmd = "bash '$wslSrc/scripts/install.sh' --from-source '$wslSrc' $($extra -join ' ')"
} else {
  $cmd = "curl -fsSL $RawUrl | bash -s -- $($extra -join ' ')"
}
Say "Inside WSL: $cmd"
Say "(you may be asked for your Linux password so apt can install build-essential and python3-dev)"
if (-not $DryRun) {
  & wsl.exe -d $Distro -e bash -lc $cmd
  if ($LASTEXITCODE -ne 0) { Die "the Linux-side installer failed (exit $LASTEXITCODE). Its messages are above." }
}

# ---- 3. shortcuts ------------------------------------------------------------------------------------------------
if ($NoShortcuts) { Say "Skipping shortcuts."; exit 0 }
$home_ = if ($ShortcutRoot) { $ShortcutRoot } else { "" }
$appDir = if ($home_) { Join-Path $home_ "PythiaStudio" } else { Join-Path $env:LOCALAPPDATA "PythiaStudio" }
$startMenu = if ($home_) { Join-Path $home_ "StartMenu" } else { [Environment]::GetFolderPath("Programs") }
$desktop = if ($home_) { Join-Path $home_ "Desktop" } else { [Environment]::GetFolderPath("Desktop") }
$binPath = if ($WslPrefix) { "$WslPrefix/venv/bin/pythia-studio" } else { "`$HOME/.pythia-studio/venv/bin/pythia-studio" }
$run = "exec $binPath"
if ($DryRun) { Say "[dry run] would create: $appDir\pythia-studio.cmd, $startMenu\PYTHIA Studio.lnk, $desktop\PYTHIA Studio.lnk"; exit 0 }
foreach ($d in @($appDir, $startMenu, $desktop)) { New-Item -ItemType Directory -Force $d | Out-Null }

# icon: the same "P" mark the app serves, written as an .ico (PNG-in-ICO) by the freshly installed package
$ico = Join-Path $appDir "pythia.ico"
$wslIco = (& wsl.exe -d $Distro -e wslpath -a $ico).Trim()
& wsl.exe -d $Distro -e bash -lc "$binPath --export-icon '$wslIco'" 2>$null
if (-not (Test-Path $ico)) { $ico = $null }

$cmdFile = Join-Path $appDir "pythia-studio.cmd"
Set-Content -Path $cmdFile -Encoding ascii -Value "@echo off`r`nwsl.exe -d $Distro -e bash -lc `"$run %*`""
Say "Created $cmdFile  (run `pythia-studio --app` from any Windows terminal once $appDir is on your PATH)"

$ws = New-Object -ComObject WScript.Shell
foreach ($dir in @($startMenu, $desktop)) {
  $lnk = $ws.CreateShortcut((Join-Path $dir "PYTHIA Studio.lnk"))
  $lnk.TargetPath = "wsl.exe"
  $lnk.Arguments = "-d $Distro -e bash -lc `"$run --app`""
  $lnk.WindowStyle = 7                       # minimized console; closing the app window stops the server
  $lnk.Description = "PYTHIA Studio: verified C++ acceleration for Python"
  if ($ico) { $lnk.IconLocation = $ico }
  $lnk.Save()
  Say "Created shortcut: $dir\PYTHIA Studio.lnk"
}
if (-not $ShortcutRoot) {
  $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
  if (($userPath -split ";") -notcontains $appDir) {
    [Environment]::SetEnvironmentVariable("Path", ($userPath.TrimEnd(";") + ";" + $appDir), "User")
    Say "Added $appDir to your user PATH (open a new terminal to use `pythia-studio`)."
  }
}
Write-Host ""
Say "Done. Start 'PYTHIA Studio' from the Start Menu or Desktop. Add --offline in the shortcut to run the demo without an API key."
