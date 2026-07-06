@echo off
setlocal

set "PAUSE_ON_EXIT=0"
if "%~1"=="" set "PAUSE_ON_EXIT=1"
set "SHOW_REVIEW_DIR=0"

set "ROOT=%~dp0"
if not exist "%ROOT%scripts\validation\generate_alpha_discovery_candidates.py" (
    set "ROOT=%USERPROFILE%\Desktop\futures_intraday_model\"
)
cd /d "%ROOT%"
if errorlevel 1 (
    echo FAILED: could not enter repo root "%ROOT%"
    set "EXIT_CODE=1"
    goto :finish
)
if not exist "%ROOT%scripts\validation\generate_alpha_discovery_candidates.py" (
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
if "%~1"=="" goto :default_run
goto :custom_run

:self_check
python -m scripts.validation.generate_alpha_discovery_candidates --self-check --launcher-path "%~f0"
set "EXIT_CODE=%ERRORLEVEL%"
goto :finish

:default_run
python -m scripts.validation.generate_alpha_discovery_candidates --generate-candidates --write-review-packet --select-implementation --max-ideas 10
set "EXIT_CODE=%ERRORLEVEL%"
set "SHOW_REVIEW_DIR=1"
goto :finish

:custom_run
python -m scripts.validation.generate_alpha_discovery_candidates --generate-candidates --write-review-packet %*
set "EXIT_CODE=%ERRORLEVEL%"
set "SHOW_REVIEW_DIR=1"
goto :finish

:finish
if "%SHOW_REVIEW_DIR%"=="1" if "%EXIT_CODE%"=="0" (
    echo.
    echo Review generated strategy candidates here:
    echo %ROOT%reports\pipeline_audit\strategy_candidate_ideation
)
if "%PAUSE_ON_EXIT%"=="1" (
    echo.
    echo RUN_STRATEGY_CANDIDATE_IDEATION.bat finished with exit code %EXIT_CODE%.
    pause
)
exit /b %EXIT_CODE%
