# Create startup shortcut for KnobDeck

$ProjectRoot = "C:\Keyboard\Keys\python_host"
$StartupFolder = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$ShortcutPath = Join-Path $StartupFolder "KnobDeck.lnk"
$LegacyShortcutPath = Join-Path $StartupFolder "Legacy Knob Menu.lnk"
$AppScript = Join-Path $ProjectRoot "knobdeck_app.py"

$PythonCandidates = @(
    (Join-Path $ProjectRoot "venv\Scripts\pythonw.exe"),
    (Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"),
    "C:\Python314\pythonw.exe",
    "C:\Python313\pythonw.exe",
    "C:\Python312\pythonw.exe"
)

$Pythonw = $PythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $Pythonw) {
    throw "Could not find a pythonw.exe interpreter for the wheel app."
}

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Pythonw
$Shortcut.Arguments = "`"$AppScript`""
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.Description = "KnobDeck"
$IconPath = Join-Path $ProjectRoot "assets\knobdeck.ico"
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = "$IconPath,0"
} else {
    $Shortcut.IconLocation = "C:\Windows\System32\shell32.dll,176"
}
$Shortcut.Save()

# Remove possible legacy shortcut names from earlier builds.
$PossibleLegacyShortcuts = @(
    $LegacyShortcutPath
)
foreach ($legacy in $PossibleLegacyShortcuts) {
    if (Test-Path $legacy) {
        Remove-Item -LiteralPath $legacy -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Shortcut created successfully at: $ShortcutPath"
Write-Host "Target: $Pythonw"
Write-Host "App: $AppScript"
Write-Host "KnobDeck will now start automatically on boot."
