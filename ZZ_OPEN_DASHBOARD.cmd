@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "DASHBOARD=%~dp0reports\visualizations\dashboard.html"
set "LOG=%~dp0reports\visualizations\dashboard_rebuild.log"

echo Rebuilding dashboard from current saved reports...
echo Working folder: %CD%
echo.

set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
set "PYTHON_ARGS="

if not exist "%PYTHON_CMD%" (
  where python >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_CMD=python"
  ) else (
    where py >nul 2>nul
    if not errorlevel 1 (
      set "PYTHON_CMD=py"
      set "PYTHON_ARGS=-3"
    ) else (
      echo Python was not found by cmd.exe.
      echo Expected path was:
      echo %LOCALAPPDATA%\Programs\Python\Python311\python.exe
      echo.
      pause
      exit /b 1
    )
  )
)

echo Using Python: %PYTHON_CMD% %PYTHON_ARGS%
echo Fast mode: skips heavy prediction-parquet diagnostics for quick launch.
echo Log: %LOG%
echo.

"%PYTHON_CMD%" %PYTHON_ARGS% -u scripts\build_metric_visualizations.py --fast --reports-dir reports --out-dir reports\visualizations --inventory reports\report_inventory.json > "%LOG%" 2>&1
set "BUILD_EXIT=%errorlevel%"
type "%LOG%"
echo.

if not "%BUILD_EXIT%"=="0" (
  echo Dashboard rebuild failed. Log:
  echo %LOG%
  pause
  exit /b %BUILD_EXIT%
)

if not exist "%DASHBOARD%" (
  echo Dashboard file was not found:
  echo %DASHBOARD%
  pause
  exit /b 1
)

echo Opening dashboard...
start "" "%DASHBOARD%"
echo Done.
timeout /t 3 >nul
