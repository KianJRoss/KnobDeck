"""
Integrations Plugin

Adds a dedicated integrations menu for:
- Discord
- OBS
- Steam
- SignalRGB
"""

import logging
import os
import subprocess
import time
import webbrowser
from typing import Dict, List, Callable

from menu_system import MenuMode, AppState, ModeHandler

logger = logging.getLogger("KeychronApp.Integrations")
state_machine_ref = None
SETTINGS = {
    "discord_mute_hotkey": "ctrl+shift+m",
    "discord_deafen_hotkey": "ctrl+shift+d",
    "discord_overlay_hotkey": "shift+`",
    "obs_record_hotkey": "ctrl+shift+r",
    "obs_stream_hotkey": "ctrl+shift+s",
    "steam_library_url": "steam://open/library",
    "steam_friends_url": "steam://open/friends",
    "steam_screenshots_url": "steam://open/screenshots",
}


def configure(settings: Dict[str, object]):
    """Optional plugin configuration entrypoint."""
    if not isinstance(settings, dict):
        return
    for key in list(SETTINGS.keys()):
        if key in settings and settings[key] is not None:
            SETTINGS[key] = str(settings[key])


def _send_hotkey(hotkey: str) -> bool:
    try:
        import keyboard as kb_lib
        kb_lib.send(hotkey)
        return True
    except Exception as e:
        logger.warning(f"Hotkey failed ({hotkey}): {e}")
        return False


def _launch_obs() -> bool:
    candidates = [
        r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
        r"C:\Program Files (x86)\obs-studio\bin\64bit\obs64.exe",
    ]
    for exe in candidates:
        if os.path.exists(exe):
            try:
                subprocess.Popen([exe], close_fds=True)
                return True
            except Exception:
                continue
    try:
        subprocess.Popen(["cmd", "/c", "start", "", "obs://"], shell=False)
        return True
    except Exception:
        return False


def _steam_url(url: str) -> bool:
    try:
        webbrowser.open(url)
        return True
    except Exception:
        return False


class _ActionWheelHandler(ModeHandler):
    """Generic 3-slot action wheel handler for integration submenus."""

    def __init__(self, state_machine, title: str, actions: List[Dict[str, Callable]]):
        self.sm = state_machine
        self.title = title
        self.actions = actions

    def on_enter(self, state: AppState):
        state.submenu_index = 0

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        if not self.actions:
            return
        if clockwise:
            state.submenu_index = (state.submenu_index + 1) % len(self.actions)
        else:
            state.submenu_index = (state.submenu_index - 1) % len(self.actions)

    def on_press(self, state: AppState):
        if not self.actions:
            return
        action = self.actions[state.submenu_index]
        callback = action.get("action")
        if callable(callback):
            callback()

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        if not self.actions:
            return {"left": "", "center": "No actions", "right": "", "title": self.title}
        total = len(self.actions)
        idx = state.submenu_index % total
        prev_idx = (idx - 1) % total
        next_idx = (idx + 1) % total
        current = self.actions[idx]
        subtitle = str(current.get("subtitle", "")).strip()
        return {
            "left": str(self.actions[prev_idx].get("name", "")),
            "center": f"> {str(current.get('name', ''))}",
            "right": str(self.actions[next_idx].get("name", "")),
            "title": self.title,
            "subtitle": subtitle,
            "active_index": 1,
        }


class IntegrationsMenuHandler(ModeHandler):
    """Top-level integrations submenu."""

    def __init__(self, state_machine):
        self.sm = state_machine
        self.items = [
            {"name": "Discord", "mode": MenuMode.INTEGRATION_DISCORD},
            {"name": "OBS Studio", "mode": MenuMode.INTEGRATION_OBS},
            {"name": "Steam", "mode": MenuMode.INTEGRATION_STEAM},
            {"name": "SignalRGB+", "mode": MenuMode.INTEGRATION_SIGNALRGB},
        ]

    def on_enter(self, state: AppState):
        state.submenu_index = 0

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        if clockwise:
            state.submenu_index = (state.submenu_index + 1) % len(self.items)
        else:
            state.submenu_index = (state.submenu_index - 1) % len(self.items)

    def on_press(self, state: AppState):
        selected = self.items[state.submenu_index]
        self.sm.enter_mode(selected["mode"])

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        total = len(self.items)
        idx = state.submenu_index % total
        prev_idx = (idx - 1) % total
        next_idx = (idx + 1) % total
        return {
            "left": self.items[prev_idx]["name"],
            "center": f"> {self.items[idx]['name']}",
            "right": self.items[next_idx]["name"],
            "title": "Integrations",
            "subtitle": "Discord, OBS, Steam, SignalRGB",
            "active_index": 1,
        }


def _discord_actions(sm):
    def _mute():
        ok = _send_hotkey(SETTINGS["discord_mute_hotkey"])
        sm.show_notification("Discord: Toggle Mute" if ok else "Discord mute hotkey failed", 1200 if ok else 1800)

    def _deafen():
        ok = _send_hotkey(SETTINGS["discord_deafen_hotkey"])
        sm.show_notification("Discord: Toggle Deafen" if ok else "Discord deafen hotkey failed", 1200 if ok else 1800)

    def _overlay():
        ok = _send_hotkey(SETTINGS["discord_overlay_hotkey"])
        sm.show_notification("Discord: Toggle Overlay" if ok else "Discord overlay hotkey failed", 1200 if ok else 1800)

    return [
        {"name": "Toggle Mute", "subtitle": "Ctrl+Shift+M", "action": _mute},
        {"name": "Toggle Deafen", "subtitle": "Ctrl+Shift+D", "action": _deafen},
        {"name": "Toggle Overlay", "subtitle": "Shift+`", "action": _overlay},
    ]


def _obs_actions(sm):
    def _record():
        ok = _send_hotkey(SETTINGS["obs_record_hotkey"])
        sm.show_notification("OBS: Toggle Recording" if ok else "OBS recording hotkey failed", 1200 if ok else 1800)

    def _stream():
        ok = _send_hotkey(SETTINGS["obs_stream_hotkey"])
        sm.show_notification("OBS: Toggle Streaming" if ok else "OBS streaming hotkey failed", 1200 if ok else 1800)

    def _launch():
        ok = _launch_obs()
        sm.show_notification("Opening OBS" if ok else "OBS not found", 1200 if ok else 1800)

    return [
        {"name": "Toggle Record", "subtitle": "Ctrl+Shift+R (set in OBS)", "action": _record},
        {"name": "Toggle Stream", "subtitle": "Ctrl+Shift+S (set in OBS)", "action": _stream},
        {"name": "Open OBS", "subtitle": "Launch OBS Studio", "action": _launch},
    ]


def _steam_actions(sm):
    def _library():
        ok = _steam_url(SETTINGS["steam_library_url"])
        sm.show_notification("Opening Steam Library" if ok else "Steam launch failed", 1200 if ok else 1800)

    def _friends():
        ok = _steam_url(SETTINGS["steam_friends_url"])
        sm.show_notification("Opening Steam Friends" if ok else "Steam launch failed", 1200 if ok else 1800)

    def _screenshots():
        ok = _steam_url(SETTINGS["steam_screenshots_url"])
        sm.show_notification("Opening Steam Screenshots" if ok else "Steam launch failed", 1200 if ok else 1800)

    return [
        {"name": "Library", "subtitle": "steam://open/library", "action": _library},
        {"name": "Friends", "subtitle": "steam://open/friends", "action": _friends},
        {"name": "Screenshots", "subtitle": "steam://open/screenshots", "action": _screenshots},
    ]


def _signalrgb_actions(sm):
    def _open():
        controller = getattr(sm, "signalrgb", None)
        ok = controller.open_signalrgb() if controller else False
        sm.show_notification("Opening SignalRGB" if ok else "SignalRGB not found", 1200 if ok else 1800)

    def _resync():
        controller = getattr(sm, "signalrgb", None)
        ok = controller.sync_if_signalrgb_mode() if controller else False
        sm.show_notification("SignalRGB resynced" if ok else "SignalRGB sync failed", 1200 if ok else 1800)

    def _random():
        controller = getattr(sm, "signalrgb", None)
        if not controller:
            sm.show_notification("SignalRGB unavailable", 1800)
            return
        ok, name = controller.apply_random_effect()
        sm.show_notification(f"Effect: {name}" if ok and name else ("Random effect applied" if ok else "No effects available"), 1500 if ok else 1800)

    return [
        {"name": "Open App", "subtitle": "Launch SignalRGB", "action": _open},
        {"name": "Resync Device", "subtitle": "Re-pulse keyboard bridge", "action": _resync},
        {"name": "Random Effect", "subtitle": "Apply random installed effect", "action": _random},
    ]


def get_commands():
    return [
        {
            "name": "Integrations",
            "description": "Discord, OBS, Steam, SignalRGB controls",
            "callback": lambda: state_machine_ref.enter_mode(MenuMode.INTEGRATIONS_MENU),
        }
    ]


def get_mode_handlers(state_machine):
    global state_machine_ref
    state_machine_ref = state_machine

    return {
        MenuMode.INTEGRATIONS_MENU: IntegrationsMenuHandler(state_machine),
        MenuMode.INTEGRATION_DISCORD: _ActionWheelHandler(state_machine, "Discord", _discord_actions(state_machine)),
        MenuMode.INTEGRATION_OBS: _ActionWheelHandler(state_machine, "OBS Studio", _obs_actions(state_machine)),
        MenuMode.INTEGRATION_STEAM: _ActionWheelHandler(state_machine, "Steam", _steam_actions(state_machine)),
        MenuMode.INTEGRATION_SIGNALRGB: _ActionWheelHandler(state_machine, "SignalRGB+", _signalrgb_actions(state_machine)),
    }
