# Custom Plugins

Drop `.py` plugin files in this folder to extend the knob menu without editing core files.

## Supported plugin exports

- `get_commands() -> list[dict]`
  - Each dict: `{"name": str, "description": str, "callback": callable}`
- `get_mode_handlers(state_machine) -> dict`
  - Return extra `MenuMode -> handler` mappings.

## Minimal command plugin

```python
def get_commands():
    return [
        {
            "name": "My Action",
            "description": "Run my custom logic",
            "callback": lambda: print("Custom plugin action"),
        }
    ]
```

Plugins in this folder are loaded at startup from `app_settings.plugin_dirs`.
