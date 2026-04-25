# Contributing

Thanks for contributing to KnobDeck.

## Project Areas
- `python_host/`: Windows app runtime (Qt, plugins, integrations)
- `sdk/plugins/`: plugin author templates
- `sdk/firmware/`: firmware bridge templates for QMK boards
- `docs-site/`: GitHub Pages site

## Development Setup
```powershell
cd python_host
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python knobdeck_app.py --no-detach
```

## Pull Request Rules
1. Keep changes scoped to one area if possible.
2. Include test/validation steps in PR description.
3. For keyboard support changes, include VID/PID evidence (`list_devices.py` output).
4. For plugin changes, include `plugin.json` schema updates.
5. For firmware templates, include board and keymap target path.

## Adding Keyboard Profiles
1. Edit `python_host/device_profiles.py`.
2. Add profile with VID/PID, usage page/usage, notes.
3. Verify detection via app Settings > General > Auto-Detect Keyboard.

## Adding Plugins
1. Start from `sdk/plugins/template_plugin`.
2. Place implementation in `python_host/custom_plugins` or `python_host/plugins`.
3. Provide a manifest (`*.plugin.json` or `plugin.json`).
