# Knob Keyboard Compatibility Research

This project targets keyboards that satisfy all of the following:

1. QMK firmware availability (or compatible fork)
2. VIA support for keymap/macros
3. Rotary encoder support (`encoder_update_user` / `encoder_map` paths)
4. Stable VID/PID + HID usage mapping for profile detection

## Priority Targets

- Keychron V1 (validated baseline)
- Keychron Q-series knob models (Q1/Q3 family)
- Glorious GMMK Pro
- Drop Sense75
- Keebio BDN9 (great encoder development target)
- MonsGeek M1 QMK edition

## Why These Work

- They are commonly documented in QMK/VIA workflows.
- They expose encoder hooks in firmware.
- Community firmware support is active, which lowers onboarding cost for contributors.

## Integration Checklist Per Keyboard

- Add profile to `python_host/device_profiles.py`
- Verify VID/PID via local device enumeration
- Confirm gesture key emissions (F13..F18)
- Validate VIA keymap stability (typing/macros unaffected)
- Validate app command path (menu, macro mode, integrations)

## Important Notes

- VID/PID can vary by production batch/region and firmware flavor.
- Profile entries are seed values; contributors should submit PR updates after device verification.
