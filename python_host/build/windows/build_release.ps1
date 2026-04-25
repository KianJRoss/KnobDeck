param(
    [string]$Version = "0.2.0"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pythonHost = Resolve-Path (Join-Path $root "..")
Set-Location $pythonHost

Write-Host "[1/4] Installing build dependencies..."
python -m pip install --upgrade pip
python -m pip install pyinstaller

Write-Host "[2/4] Building executable..."
python -m PyInstaller --noconfirm build\\windows\\KnobDeck.spec

Write-Host "[3/4] Compiling installer (requires ISCC in PATH)..."
$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) {
    Write-Warning "Inno Setup compiler (iscc) not found in PATH. Skipping installer build."
    exit 0
}
& $iscc.Path "build\windows\installer.iss" "/DAppVersion=$Version"

Write-Host "[4/4] Done. Installer output: dist\\installer"

