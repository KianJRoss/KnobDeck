# QMK Firmware SDK (Encoder Bridge)

This template shows how to adapt another knob keyboard firmware for this app.

## Goal
- Keep keyboard keys and VIA working normally.
- Emit encoder gestures as dedicated host shortcuts (`F13`..`F18`) for the app.

## Event mapping
- `F13`: rotate clockwise
- `F14`: rotate counter-clockwise
- `F15`: encoder press
- `F16`: encoder release
- `F17`: long press
- `F18`: double click

## Steps
1. Start from your board's official QMK keymap.
2. Merge logic from `keymap.c.template`.
3. Build and flash with `qmk compile` / `qmk flash`.
4. In app Settings, select the matching keyboard profile.

## Notes
- Do not break VIA dynamic keymap handling.
- Keep knob handling on firmware side; app reads only gesture hotkeys.
- If your board uses different HID usages, add/update a profile in `python_host/device_profiles.py`.
