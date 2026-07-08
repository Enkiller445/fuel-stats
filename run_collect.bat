@echo off
rem ----------------------------------------------------------------------
rem  Optional LOCAL run (fallback if you don't use GitHub Actions).
rem  Collects both sources and rebuilds index.html.
rem  Double-click: collect + open dashboard.  /quiet: no browser popup.
rem ----------------------------------------------------------------------
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python run.py
set RC=%errorlevel%
if "%~1"=="/quiet" exit /b %RC%
if "%RC%"=="0" (
  start "" "public\index.html"
) else (
  echo.
  echo Collection had errors - see the log above.
  pause
)
exit /b %RC%
