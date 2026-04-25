# KnobDeck Host App (Python/Qt)

KnobDeck is a Windows desktop app for knob-equipped keyboards.

It combines:
- radial menu + macro workflows,
- plugin integrations (OBS/Discord/Steam/etc.),
- profile-aware keyboard support,
- optional SignalRGB and Voicemeeter controls.

## Quick Start

```powershell
cd python_host
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python knobdeck_app.py --no-detach
```

## Keyboard Profiles

Profiles are defined in `device_profiles.py` and include VID/PID + capabilities.

Use Settings -> General:
- `Keyboard profile` dropdown for manual selection
- `Auto-Detect Keyboard` to match connected devices

## Plugin System

Built-in plugins are in `python_host/plugins/`.
Custom plugins go in `python_host/custom_plugins/`.

Use the SDK starter in `sdk/plugins/template_plugin`.
Manifests (`*.plugin.json`) provide metadata and schema-driven settings UI.

## Firmware Bridge Model

Firmware should emit gesture shortcuts (`F13`..`F18`) so typing + VIA keep working while the app handles knob actions.

Template files:
- `sdk/firmware/qmk_encoder_bridge/keymap.c.template`
- `sdk/firmware/qmk_encoder_bridge/rules.mk.template`

## Windows Packaging

- PyInstaller spec: `build/windows/KnobDeck.spec`
- Inno Setup script: `build/windows/installer.iss`
- Local build script: `build/windows/build_release.ps1`
- CI workflows:
  - `.github/workflows/windows-release.yml`
  - `.github/workflows/smoke-tests.yml`

## Dependency Files

- Runtime: `requirements.txt`
- Build-only: `requirements-build.txt`
- Locked baseline: `requirements-lock.txt`

## Docs Site

GitHub Pages content lives in `docs-site/` and deploys via `.github/workflows/pages.yml`.
