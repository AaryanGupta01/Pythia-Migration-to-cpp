@echo off
rem PYTHIA Studio launcher for Windows: runs the app inside WSL2 (it needs a Linux C++ toolchain) and opens the browser.
rem   studio.cmd [--offline] [--port N] [--app] [--no-open]
setlocal
where wsl >nul 2>nul
if errorlevel 1 (
  echo PYTHIA Studio needs WSL2 on Windows. Open PowerShell as administrator, run:  wsl --install
  echo then reboot and run  powershell -ExecutionPolicy Bypass -File scripts\install.ps1
  exit /b 1
)
for /f "delims=" %%i in ('wsl -e wslpath -a "%~dp0."') do set WSLDIR=%%i
set ARGS=%*
wsl -e bash -lc "cd '%WSLDIR%' && sed -i 's/\r$//' studio.sh scripts/*.sh 2>/dev/null; bash ./studio.sh %ARGS%"
