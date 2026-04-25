# Repository Guidelines

## Project Structure & Module Organization
KnobDeck is split into a Windows host app, SDK templates, and docs.

- `python_host/`: main desktop app (PyQt6), menu logic, integrations, plugins, packaging scripts.
- `python_host/plugins/`: built-in plugins. `python_host/custom_plugins/`: user/third-party plugins.
- `sdk/plugins/template_plugin/`: starter template for plugin authors.
- `sdk/firmware/qmk_encoder_bridge/`: QMK bridge templates for knob keyboards.
- `docs-site/`: GitHub Pages website content.
- `.github/workflows/`: CI for Windows releases and Pages deployment.

## Build, Test, and Development Commands
Run from repo root unless noted.

- `powershell ./install_windows.ps1`: create venv and install dependencies.
- `cd python_host; .\\venv\\Scripts\\python.exe knobdeck_app.py --no-detach`: run app in foreground.
- `cd python_host; .\\venv\\Scripts\\python.exe list_devices.py`: enumerate HID devices.
- `./build_auto.bat`: build main QMK keymap (`raw_hid_menu`).
- `./build_via_restore.bat`: build VIA-safe recovery firmware.

## Coding Style & Naming Conventions
- Python: 4 spaces, `snake_case` for functions/files, `PascalCase` for classes.
- Keep modules feature-scoped (`signalrgb_control.py`, `voicemeeter_api.py`).
- Plugin manifests use JSON and should include name, version, and settings schema.
- Follow existing style in touched files; avoid unrelated formatting churn.

## Testing Guidelines
- Validate app startup: run `knobdeck_app.py` and confirm tray + menu rendering.
- For integrations, run targeted scripts in `python_host/` (for example `test_display.py`).
- Firmware changes must compile successfully and produce `.bin` artifacts in `qmk_firmware/.build/`.

## Commit & Pull Request Guidelines
- Commit format: `<area>: <imperative summary>` (example: `python_host: fix submenu toggle debounce`).
- Keep commits focused and explain user-visible behavior changes.
- PRs should include: problem, fix summary, validation steps, and screenshots for UI changes.
- For device support changes, include VID/PID evidence and tested keyboard profile.

## Security & Configuration Tips
- Do not commit local secrets or machine-specific config (`python_host/config.local.json`, `.env`).
- Keep large local mirrors (`qmk_firmware/`, `firmware_baselines/`) out of PRs unless intentionally updated.
