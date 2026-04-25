@echo off
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0download_installer.ps1" %*
exit /b %errorlevel%
