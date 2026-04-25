# Keychron V1 Menu System Installer
# Run this from a PowerShell terminal

$ProjectRoot = Get-Location
$PythonHostDir = Join-Path $ProjectRoot "python_host"
$VenvDir = Join-Path $PythonHostDir "venv"

Write-Host "--- Keychron V1 Menu System Installer ---" -ForegroundColor Cyan

# 1. Check for Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Found $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: Python is not installed or not in PATH." -ForegroundColor Red
    exit
}

# 2. Create Virtual Environment
Write-Host "Creating virtual environment in $VenvDir..." -ForegroundColor Yellow
python -m venv $VenvDir

# 3. Install Dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
$PipPath = Join-Path $VenvDir "Scripts\pip.exe"
$ReqPath = Join-Path $PythonHostDir "requirements.txt"
& $PipPath install -r $ReqPath

# 4. Create Desktop Shortcut
Write-Host "Creating Desktop shortcut..." -ForegroundColor Yellow
$WshShell = New-Object -ComObject WScript.Shell
$ShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Keychron Menu.lnk"
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = Join-Path $VenvDir "Scripts\pythonw.exe"  # pythonw hides the console
$Shortcut.Arguments = "`"$(Join-Path $PythonHostDir 'keychron_app_qt.py')`""
$Shortcut.WorkingDirectory = $PythonHostDir
$Shortcut.IconLocation = "shell32.dll,44" # Keyboard icon
$Shortcut.Save()

Write-Host "`nInstallation complete!" -ForegroundColor Green
Write-Host "You can now launch the system from the 'Keychron Menu' shortcut on your Desktop."
Write-Host "Note: Flash the raw_hid_menu keymap to keep VIA key/lighting control while knob events drive the menu app."
