@echo off
setlocal
cd /d "%~dp0"
title PZ-REVIZE - sestaveni EXE

where py >nul 2>nul
if errorlevel 1 (
  echo Python nebyl nalezen.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt
if errorlevel 1 goto :err

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist PZ-REVIZE.spec del /q PZ-REVIZE.spec

python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --collect-submodules "reportlab.graphics.barcode" ^
  --hidden-import "reportlab.graphics.barcode.code93" ^
  --name "PZ-REVIZE" ^
  --icon "pzrevize\resources\pz_revize.ico" ^
  --add-data "pzrevize\resources;pzrevize\resources" ^
  app.py

if errorlevel 1 goto :err

echo.
echo HOTOVO: dist\PZ-REVIZE.exe
pause
goto :eof

:err
echo.
echo Sestaveni EXE se nezdarilo. Zkopirujte chybovou hlasku a poslete ji do chatu.
pause
exit /b 1
