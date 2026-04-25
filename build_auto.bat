@echo off
setlocal

REM One-command QMK build with clear success/failure checks.

set "QMK_DIR=C:\QMK_MSYS"
set "QMK_SHELL=%QMK_DIR%\shell_connector.cmd"
set "FW_DIR=C:\Keyboard\Keys\qmk_firmware"
set "KEYBOARD=keychron/v1/ansi_encoder"
set "KEYMAP=raw_hid_menu"
set "BIN_NAME=keychron_v1_ansi_encoder_raw_hid_menu.bin"
set "BIN_PATH=%FW_DIR%\.build\%BIN_NAME%"
set "BUILD_CMD=cd /c/Keyboard/Keys/qmk_firmware && qmk compile -kb %KEYBOARD% -km %KEYMAP%"

echo ========================================
echo QMK Auto Build
echo ========================================
echo Keyboard : %KEYBOARD%
echo Keymap   : %KEYMAP%
echo Output   : %BIN_PATH%
echo.

if not exist "%QMK_SHELL%" (
    echo ERROR: QMK shell launcher not found:
    echo   %QMK_SHELL%
    exit /b 2
)

echo Starting compile...
echo.
"%QMK_SHELL%" -lc "%BUILD_CMD%"
set "BUILD_EXIT=%ERRORLEVEL%"

echo.
if not "%BUILD_EXIT%"=="0" (
    echo ========================================
    echo BUILD FAILED (exit code %BUILD_EXIT%)
    echo ========================================
    exit /b %BUILD_EXIT%
)

if not exist "%BIN_PATH%" (
    echo ========================================
    echo BUILD FAILED (no output binary found)
    echo ========================================
    exit /b 3
)

for %%F in ("%BIN_PATH%") do (
    set "BIN_SIZE=%%~zF"
    set "BIN_TIME=%%~tF"
)

echo ========================================
echo BUILD SUCCESS
echo ========================================
echo Binary   : %BIN_PATH%
echo Size     : %BIN_SIZE% bytes
echo Modified : %BIN_TIME%
echo.

exit /b 0

