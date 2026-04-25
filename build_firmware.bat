@echo off
REM Keychron V1 Raw HID Menu - Build Script
REM This opens QMK MSYS and runs the compile command

set "QMK_DIR=C:\QMK_MSYS"
set "BUILD_CMD=cd /c/Keyboard/Keys/qmk_firmware && qmk compile -kb keychron/v1/ansi_encoder -km raw_hid_menu && echo. && echo ======================================== && echo Build Complete! && echo ======================================== && echo. && echo Firmware file: && ls -lh .build/keychron_v1_ansi_encoder_raw_hid_menu.bin 2>/dev/null && echo."
set "QMK_SHELL=%QMK_DIR%\shell_connector.cmd"

echo ========================================
echo Keychron V1 Raw HID Menu - Build Script
echo ========================================
echo.
echo Opening QMK MSYS terminal to compile...
echo.

REM Launch using QMK's shell connector (matches working QMK terminal behavior)
if exist "%QMK_SHELL%" (
    "%QMK_SHELL%" -lc "%BUILD_CMD%"
) else if exist "%QMK_DIR%\msys2_shell.cmd" (
    "%QMK_DIR%\msys2_shell.cmd" -mingw64 -defterm -no-start -here -c "%BUILD_CMD%"
) else if exist "%QMK_DIR%\usr\bin\bash.exe" (
    "%QMK_DIR%\usr\bin\bash.exe" -lc "%BUILD_CMD%"
) else (
    echo ERROR: QMK shell not found in %QMK_DIR%
    echo Expected one of:
    echo   %QMK_SHELL%
    echo   %QMK_DIR%\msys2_shell.cmd
    echo   %QMK_DIR%\usr\bin\bash.exe
)

echo.
pause
