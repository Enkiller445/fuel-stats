@echo off
rem ----------------------------------------------------------------------
rem  One-time helper: push this folder to a new (empty) GitHub repository.
rem  1) Create an empty repo on github.com (no README/license).
rem  2) Copy its URL, e.g. https://github.com/USER/REPO.git
rem  3) Double-click this file and paste the URL when asked.
rem  The first push opens a browser to sign in to GitHub (one time).
rem ----------------------------------------------------------------------
cd /d "%~dp0"
set /p REPO="Paste your empty GitHub repo URL: "
if "%REPO%"=="" ( echo No URL entered. & pause & exit /b 1 )

git init
git config user.email "fuelstats@local"
git config user.name "Fuel Stats"
git add -A
git commit -m "Fuel stats: collector + single-page dashboard"
git branch -M main
git remote remove origin 2>nul
git remote add origin %REPO%
git push -u origin main

echo.
echo Done. Next: on GitHub open Settings -> Pages, and Settings -> Actions (see README).
pause
