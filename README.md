# KnobDeck

KnobDeck is an open-source platform for encoder/knob keyboards.

It provides:
- a Windows radial menu app with macro layers,
- plugin integrations (audio, apps, lighting, productivity),
- keyboard profile support for multiple QMK/VIA boards,
- firmware bridge templates for new devices,
- CI packaging and installer pipelines.

## Repository Map

- `python_host/` - main desktop app (PyQt6)
- `sdk/plugins/` - plugin starter templates
- `sdk/firmware/` - firmware bridge templates for QMK boards
- `docs-site/` - GitHub Pages static website
- `.github/workflows/windows-release.yml` - build portable + installer artifacts
- `.github/workflows/pages.yml` - deploy docs site

## Install (EXE)

Use the Windows installer from Releases:
- `KnobDeck-Setup-<version>.exe`
- https://github.com/KianJRoss/KnobDeck/releases

Build locally:

```bat
build_installer.bat
```

## Start App

```powershell
cd python_host
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python knobdeck_app.py --no-detach
```

## Open Source Contributions

See:
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `LICENSE`
