@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo PZ-REVIZE Mobile - nastaveni JAVA_HOME
echo.
if not exist ".tools" mkdir ".tools"
del /q ".tools\java_home.txt" >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0SELECT_JAVA.ps1" -ProjectDir "%~dp0"
if errorlevel 1 goto :fail
set /p "JDK=" < ".tools\java_home.txt"
if not exist "%JDK%\bin\java.exe" goto :fail

echo.
echo Nalezeno: %JDK%
"%JDK%\bin\java.exe" -version 2>&1
setx JAVA_HOME "%JDK%" >nul
if errorlevel 1 goto :fail

echo.
echo JAVA_HOME bylo nastaveno pro nova okna prikazoveho radku.
echo Pro BUILD_APK.bat to ale neni nutne - ten si spravne JDK vybira sam.
pause
exit /b 0

:fail
echo.
echo Nastaveni JAVA_HOME selhalo.
pause
exit /b 1
