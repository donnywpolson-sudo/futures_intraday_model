@echo off
setlocal

set "ROOT=%~dp0"
if not exist "%ROOT%scripts\validation\run_alpha_discovery.py" (
    set "ROOT=%USERPROFILE%\Desktop\futures_intraday_model\"
)
cd /d "%ROOT%"
if errorlevel 1 (
    echo FAILED: could not enter repo root "%ROOT%"
    exit /b 1
)
if not exist "%ROOT%scripts\validation\run_alpha_discovery.py" (
    echo FAILED: could not find futures_intraday_model repo root at "%ROOT%"
    echo Move this launcher next to the repo or update the ROOT fallback in %~nx0.
    exit /b 1
)

python --version >nul 2>&1
if errorlevel 1 (
    echo FAILED: python is not available on PATH.
    exit /b 1
)

if /I "%~1"=="--self-check" (
    python -m scripts.validation.run_alpha_discovery_wizard --self-check --launcher-path "%~f0"
    exit /b %ERRORLEVEL%
)

if "%~1"=="" (
    python -m scripts.validation.run_alpha_discovery_wizard --launcher-path "%~f0"
    exit /b %ERRORLEVEL%
)

if /I "%~1"=="--generate-candidates" (
    python -m scripts.validation.generate_alpha_discovery_candidates %*
    exit /b %ERRORLEVEL%
)

if /I "%~1"=="--queue" (
    python -m scripts.validation.run_alpha_discovery_queue %*
    exit /b %ERRORLEVEL%
)

python -m scripts.validation.run_alpha_discovery --log-root logs\alpha_discovery %*
exit /b %ERRORLEVEL%
