param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pythonHost = Resolve-Path (Join-Path $root "..")
Set-Location $pythonHost

if ([string]::IsNullOrWhiteSpace($Version)) {
    try {
        $tag = (git describe --tags --exact-match 2>$null).Trim()
        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($tag)) {
            $Version = $tag.TrimStart('v')
        }
    } catch {
        # Keep fallback below
    }
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = "0.0.0-dev"
}

Write-Host "Using installer version: $Version"

Write-Host "[1/4] Installing build dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt

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
