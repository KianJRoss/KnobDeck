# Plugin SDK Template

Copy this folder into `python_host/custom_plugins/<your_plugin_name>` and rename files.

## Required files
- `plugin.py`: exports plugin hooks used by the app.
- `plugin.json`: metadata + settings schema shown in the Settings UI.

## Supported hooks
- `configure(settings: dict)` optional: receives schema-driven values.
- `get_commands() -> list[dict]` optional: add top-level commands.
- `get_mode_handlers(state_machine) -> dict` optional: add custom modes.

## Command format
```python
{
  "name": "Command Name",
  "description": "What it does",
  "callback": callable,
}
```

## Install locally
1. Create `python_host/custom_plugins/my_plugin/`.
2. Copy `plugin.py` + `plugin.json`.
3. Restart app or use plugin hot-reload.
