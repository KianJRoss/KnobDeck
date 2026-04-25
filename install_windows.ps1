param(
    [switch]$RunAfterInstall
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "Creating virtual environment..."
if (-not (Test-Path "python_host\venv\Scripts\python.exe")) {
    python -m venv python_host\venv
}

$python = Join-Path $root "python_host\venv\Scripts\python.exe"

Write-Host "Installing dependencies..."
& $python -m pip install --upgrade pip
& $python -m pip install -r python_host\requirements.txt

Write-Host "Creating startup shortcut helper..."
powershell -ExecutionPolicy Bypass -File python_host\create_startup_shortcut.ps1

Write-Host "Install complete."
Write-Host "Run app with: python_host\\venv\\Scripts\\python.exe python_host\\knobdeck_app.py"

if ($RunAfterInstall) {
    & $python python_host\knobdeck_app.py
}
