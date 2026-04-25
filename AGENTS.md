# Repository Guidelines

## Project Structure & Module Organization
This repo combines custom QMK firmware and a Windows Python host app.

- `qmk_firmware/`: QMK source tree (large upstream fork/vendor).
- `qmk_firmware/keyboards/keychron/v1/ansi_encoder/keymaps/raw_hid_menu/`: main custom firmware (`keymap.c`, `config.h`, `rules.mk`).
- `qmk_firmware/keyboards/keychron/v1/ansi_encoder/keymaps/via_restore/`: recovery keymap for restoring VIA behavior.
- `python_host/`: host-side app (`keychron_app.py`), UI overlays, HID/event handling, and plugin modules in `python_host/plugins/`.
- Root `*.bat` scripts: Windows build helpers for QMK MSYS.

## Build, Test, and Development Commands
Use Windows PowerShell from repo root unless noted.

- `./build_auto.bat`: compile `raw_hid_menu` firmware with success/failure checks.
- `./build_via_restore.bat`: build VIA-safe recovery firmware.
- `cd qmk_firmware; qmk compile -kb keychron/v1/ansi_encoder -km raw_hid_menu`: direct CLI build.
- `cd python_host; pip install -r requirements.txt`: install host dependencies.
- `cd python_host; python keychron_app_qt.py`: run the host app without competing with VIA for HID access.
- `cd python_host; python list_devices.py`: verify HID device detection before runtime debugging.

## Coding Style & Naming Conventions
- Python: 4-space indentation, snake_case for functions/files, PascalCase for classes (`MenuStateMachine`, `PluginManager`).
- QMK C: follow existing keymap style and QMK macros; keep constants and event IDs uppercase (`EVT_ENCODER_CW`).
- Keep plugin modules focused and named by feature (e.g., `display_control.py`, `game_mode.py`).
- No enforced formatter/linter is configured at repo root; keep changes consistent with surrounding files.

## Testing Guidelines
- Firmware changes: rebuild and confirm output in `qmk_firmware/.build/`.
- Host changes: run focused scripts in `python_host/` (for example `python test_monitor_toggle.py`, `python test_display.py`).
- Prefer small, hardware-aware validation notes in PRs (device, firmware keymap, and scenario tested).

## Commit & Pull Request Guidelines
Current commit history is short/informal; use clear, scoped commits going forward.

- Commit format: `<area>: <imperative summary>` (example: `python_host: fix HID reconnect backoff`).
- Keep one logical change per commit.
- PRs should include: purpose, impacted paths, test/build commands run, and hardware verification notes.
- Link related issue/task when available; include screenshots only for UI/overlay changes.
