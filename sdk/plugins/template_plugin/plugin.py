"""Template plugin for the knob app.

Rename this module and customize actions.
"""

from __future__ import annotations

from typing import Dict, Any, List

SETTINGS: Dict[str, Any] = {
    "enabled": True,
    "command_name": "Template Action",
    "hotkey": "ctrl+alt+t",
}


def configure(settings: Dict[str, Any]):
    """Optional settings hook called by PluginManager."""
    if isinstance(settings, dict):
        SETTINGS.update(settings)


def _trigger():
    if not SETTINGS.get("enabled", True):
        return
    try:
        import keyboard
        keyboard.send(str(SETTINGS.get("hotkey", "ctrl+alt+t")))
    except Exception:
        pass


def get_commands() -> List[Dict[str, Any]]:
    """Return commands to register in main wheel command list."""
    return [
        {
            "name": str(SETTINGS.get("command_name", "Template Action")),
            "description": "Template plugin action",
            "callback": _trigger,
        }
    ]
