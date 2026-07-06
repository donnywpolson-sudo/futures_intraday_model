@echo off
setlocal

set "PAUSE_ON_EXIT=0"
if "%~1"=="" set "PAUSE_ON_EXIT=1"

set "ROOT=%~dp0"
if not exist "%ROOT%scripts\validation\run_alpha_discovery.py" (
    set "ROOT=%USERPROFILE%\Desktop\futures_intraday_model\"
)
cd /d "%ROOT%"
if errorlevel 1 (
    echo FAILED: could not enter repo root "%ROOT%"
    set "EXIT_CODE=1"
    goto :finish
)
if not exist "%ROOT%scripts\validation\run_alpha_discovery.py" (
    echo FAILED: could not find futures_intraday_model repo root at "%ROOT%"
    echo Move this launcher next to the repo or update the ROOT fallback in %~nx0.
    set "EXIT_CODE=1"
    goto :finish
)

python --version >nul 2>&1
if errorlevel 1 (
    echo FAILED: python is not available on PATH.
    set "EXIT_CODE=1"
    goto :finish
)

if /I "%~1"=="--self-check" goto :self_check
if "%~1"=="" goto :wizard
if /I "%~1"=="--generate-candidates" goto :generate_candidates
if /I "%~1"=="--queue" goto :queue
goto :direct_run

:self_check
python -m scripts.validation.run_alpha_discovery_wizard --self-check --launcher-path "%~f0"
set "EXIT_CODE=%ERRORLEVEL%"
goto :finish

:wizard
python -m scripts.validation.run_alpha_discovery_wizard --skip-initial-ack --launcher-path "%~f0"
set "EXIT_CODE=%ERRORLEVEL%"
goto :finish

:generate_candidates
python -m scripts.validation.generate_alpha_discovery_candidates %*
set "EXIT_CODE=%ERRORLEVEL%"
goto :finish

:queue
python -m scripts.validation.run_alpha_discovery_queue %*
set "EXIT_CODE=%ERRORLEVEL%"
goto :finish

:direct_run
python -m scripts.validation.run_alpha_discovery --log-root logs\alpha_discovery %*
set "EXIT_CODE=%ERRORLEVEL%"
goto :finish

:finish
if "%PAUSE_ON_EXIT%"=="1" (
    echo.
    echo RUN_ALPHA_DISCOVERY.bat finished with exit code %EXIT_CODE%.
    pause
)
exit /b %EXIT_CODE%
