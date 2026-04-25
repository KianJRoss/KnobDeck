@echo off
setlocal

set "ROOT=%~dp0"
set "SCRIPT=%ROOT%python_host\build\windows\build_release.ps1"

if not exist "%SCRIPT%" (
    echo ERROR: Build script not found:
    echo   %SCRIPT%
    exit /b 2
)

echo Building KnobDeck installer...
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
if errorlevel 1 (
    echo.
    echo Build failed.
    exit /b %errorlevel%
)

echo.
echo Done. Installer output:
echo   %ROOT%python_host\dist\installer
exit /b 0
