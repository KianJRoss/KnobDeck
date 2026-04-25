param(
    [string]$Version = "latest",
    [string]$OutputDir = "release_downloads"
)

$ErrorActionPreference = "Stop"
$repo = "KianJRoss/KnobDeck"
$apiBase = "https://api.github.com/repos/$repo"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

if ($Version -eq "latest") {
    $release = Invoke-RestMethod -Uri "$apiBase/releases/latest"
} else {
    $tag = if ($Version.StartsWith("v")) { $Version } else { "v$Version" }
    $release = Invoke-RestMethod -Uri "$apiBase/releases/tags/$tag"
}

$asset = $release.assets | Where-Object { $_.name -like "KnobDeck-Setup-*.exe" } | Select-Object -First 1
if (-not $asset) {
    throw "No installer asset found in release $($release.tag_name)."
}

$target = Join-Path $OutputDir $asset.name
Write-Host "Downloading $($asset.name) from $($release.tag_name)..."
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $target
Write-Host "Saved installer to: $target"
