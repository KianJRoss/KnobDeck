@echo off
REM Keychron V1 Raw HID Menu - Build Script
REM Automatically compiles the firmware using QMK MSYS

set "QMK_DIR=C:\QMK_MSYS"
set "BUILD_CMD=cd /c/Keyboard/Keys/qmk_firmware && qmk compile -kb keychron/v1/ansi_encoder -km raw_hid_menu"
set "QMK_SHELL=%QMK_DIR%\shell_connector.cmd"

echo ========================================
echo Keychron V1 Raw HID Menu - Build Script
echo ========================================
echo.

REM Launch QMK MSYS with build command
if exist "%QMK_SHELL%" (
    start /wait "" "%QMK_SHELL%" -lc "%BUILD_CMD%"
) else if exist "%QMK_DIR%\msys2_shell.cmd" (
    start /wait "" "%QMK_DIR%\msys2_shell.cmd" -mingw64 -defterm -no-start -c "%BUILD_CMD%"
) else if exist "%QMK_DIR%\usr\bin\bash.exe" (
    start /wait "" "%QMK_DIR%\usr\bin\bash.exe" -lc "%BUILD_CMD%"
) else (
    echo ERROR: QMK shell not found in %QMK_DIR%
    echo Expected one of:
    echo   %QMK_SHELL%
    echo   %QMK_DIR%\msys2_shell.cmd
    echo   %QMK_DIR%\usr\bin\bash.exe
)

echo.
echo ========================================
echo Build Complete!
echo ========================================
echo.
echo Check output above for compilation status
echo Firmware location (if successful):
echo C:\Keyboard\Keys\qmk_firmware\.build\keychron_v1_ansi_encoder_raw_hid_menu.bin
echo.
pause
