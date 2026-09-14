@echo off
setlocal
cd /d "%~dp0"
title PZ-REVIZE - spusteni

echo ==========================================
echo   PZ-REVIZE - prvni spusteni / aktualizace
echo ==========================================

where py >nul 2>nul
if errorlevel 1 (
  echo Python nebyl nalezen. Nainstalujte Python 3.11 nebo novejsi a zaskrtnete "Add Python to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Vytvarim virtualni prostredi...
  py -3 -m venv .venv
  if errorlevel 1 goto :err
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :err

python app.py
goto :eof

:err
echo.
echo Spusteni se nezdarilo. Zkopirujte chybovou hlasku a poslete ji do chatu.
pause
exit /b 1
