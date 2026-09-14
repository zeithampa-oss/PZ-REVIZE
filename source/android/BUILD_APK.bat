@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title PZ-REVIZE Mobile - sestaveni APK

echo ================================================
echo   PZ-REVIZE Mobile 0.5.1 TABLET - sestaveni APK
echo ================================================
echo.

rem ------------------------------------------------
rem 1) JAVA 17/21
rem Java 25 zpusobuje s Gradle 8.9 chybu major version 69.
rem SELECT_JAVA.ps1 proto pouzije JDK 17/21, prednostne JBR Android Studia.
rem Kdyz vhodne JDK neni, stahne prenosne Temurin JDK 21 do .tools.
rem ------------------------------------------------
if not exist ".tools" mkdir ".tools"
del /q ".tools\java_home.txt" >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0SELECT_JAVA.ps1" -ProjectDir "%~dp0"
if errorlevel 1 (
  echo.
  echo CHYBA: Nepodarilo se pripravit kompatibilni JDK 17/21.
  echo Systemovou Javu 25 neni nutne odinstalovat.
  echo Zkontrolujte internet nebo instalaci Android Studia a spustte skript znovu.
  pause
  exit /b 1
)
if not exist ".tools\java_home.txt" (
  echo CHYBA: Nebyla nalezena cesta k JDK.
  pause
  exit /b 1
)
set /p "JAVA_HOME=" < ".tools\java_home.txt"
if not exist "%JAVA_HOME%\bin\java.exe" (
  echo CHYBA: Vybrane JAVA_HOME neni platne: %JAVA_HOME%
  pause
  exit /b 1
)
set "PATH=%JAVA_HOME%\bin;%PATH%"

echo.
echo Pouzite JAVA_HOME: %JAVA_HOME%
echo Java:
"%JAVA_HOME%\bin\java.exe" -version 2>&1
echo.

rem ------------------------------------------------
rem 2) Android SDK
rem ------------------------------------------------
set "SDK=%ANDROID_SDK_ROOT%"
if "%SDK%"=="" set "SDK=%ANDROID_HOME%"
if "%SDK%"=="" set "SDK=%LOCALAPPDATA%\Android\Sdk"

if not exist "%SDK%\platforms" (
  echo CHYBA: Android SDK nebylo nalezeno.
  echo.
  echo V Android Studio otevrete:
  echo   More Actions ^> SDK Manager
  echo a nainstalujte Android SDK Platform 35 a Build-Tools.
  echo.
  echo Ocekavana cesta je obvykle:
  echo   %LOCALAPPDATA%\Android\Sdk
  echo.
  pause
  exit /b 1
)

if not exist "%SDK%\platforms\android-35" (
  echo CHYBA: V Android SDK chybi Platform 35.
  echo V Android Studio otevri SDK Manager a nainstaluj Android 15 / API 35.
  pause
  exit /b 1
)

> local.properties echo sdk.dir=%SDK:\=\\%
echo Android SDK: %SDK%
echo.

rem ------------------------------------------------
rem 3) Gradle 8.9
rem ------------------------------------------------
set "GRADLE_DIR=%~dp0.tools\gradle-8.9"
set "GRADLE_EXE=%GRADLE_DIR%\bin\gradle.bat"
if not exist "%GRADLE_EXE%" (
  echo Stahuji Gradle 8.9...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $u='https://services.gradle.org/distributions/gradle-8.9-bin.zip'; $z='%~dp0.tools\gradle-8.9-bin.zip'; Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $z; Expand-Archive -Force $z '%~dp0.tools'; Remove-Item $z"
  if errorlevel 1 (
    echo.
    echo CHYBA: Stazeni Gradle se nezdarilo.
    echo Zkontrolujte internetove pripojeni a spustte skript znovu.
    pause
    exit /b 1
  )
)

rem ------------------------------------------------
rem 4) Sestaveni
rem ------------------------------------------------
echo Sestavuji APK...
call "%GRADLE_EXE%" --no-daemon clean assembleDebug
if errorlevel 1 (
  echo.
  echo Sestaveni APK selhalo.
  echo Zkopirujte sem prosim cely vypis chyby z okna.
  pause
  exit /b 1
)

set "APK=%~dp0app\build\outputs\apk\debug\app-debug.apk"
if exist "%APK%" (
  copy /Y "%APK%" "%~dp0PZ_REVIZE_MOBILE_0.5.1_TABLET_DEBUG.apk" >nul
  echo.
  echo ================================================
  echo HOTOVO
  echo %~dp0PZ_REVIZE_MOBILE_0.5.1_TABLET_DEBUG.apk
  echo ================================================
) else (
  echo.
  echo CHYBA: Sestaveni probehlo, ale APK nebylo nalezeno.
  pause
  exit /b 1
)

pause
