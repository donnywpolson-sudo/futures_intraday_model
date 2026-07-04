@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"
if errorlevel 1 (
    echo FAILED: could not enter repo root "%ROOT%"
    exit /b 1
)

python --version >nul 2>&1
if errorlevel 1 (
    echo FAILED: python is not available on PATH.
    exit /b 1
)

python -m scripts.validation.run_alpha_discovery --log-root logs\alpha_discovery %*
exit /b %ERRORLEVEL%
