# winget Manifest Scaffold

This folder contains starter manifests for publishing KnobDeck to winget.

## Files
- `KnobDeck.installer.yaml.template`
- `KnobDeck.locale.en-US.yaml.template`
- `KnobDeck.version.yaml.template`

## Publish Steps
1. Copy templates and replace placeholders:
- `__VERSION__`
- `__INSTALLER_URL__`
- `__INSTALLER_SHA256__`

2. Validate with winget tools:
```powershell
winget validate .\packaging\winget\manifests\KianJRoss\KnobDeck
```

3. Submit to `microsoft/winget-pkgs`.

Use release asset URLs from GitHub Releases:
`https://github.com/KianJRoss/KnobDeck/releases/download/vX.Y.Z/KnobDeck-Setup-X.Y.Z.exe`
