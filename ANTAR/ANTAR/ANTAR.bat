@echo off
title ANTAR
cd /d "%~dp0"

cls
echo.
echo   ============================================
echo      ANTAR
echo   ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo   Python is not installed on this PC.
  echo.
  echo   Fix:
  echo     1. Go to https://www.python.org/downloads/ in your browser
  echo     2. Click the yellow "Download Python" button
  echo     3. Run the installer
  echo     4. Tick "Add python.exe to PATH" on the first screen
  echo     5. Click Install Now
  echo     6. Come back and double-click ANTAR.bat
  echo.
  echo   Press any key to close this window.
  pause
  exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   Python found: !PYVER!
echo.

for /d /r "%~dp0" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" >nul 2>nul
del /s /q "%~dp0*.pyc" >nul 2>nul

python -m pip install --quiet -r requirements.txt
if errorlevel 1 (
  echo   Could not install the helper tools. Check your internet.
  pause
  exit /b 1
)

echo.
echo   Starting the panel...
echo   When you see "ANTAR panel READY" below, the panel is open in your browser.
echo   (Browser opens automatically. If it does not, type http://localhost:8787/ in your browser.)
echo.
echo   ============================================
echo.

REM Start the panel in this SAME window so you can see every line.
REM If python fails, the error will be visible right here.
python run.py panel

echo.
echo   ============================================
echo   The panel has stopped.
echo   Close this window, or press any key to close it now.
pause
exit /b 0