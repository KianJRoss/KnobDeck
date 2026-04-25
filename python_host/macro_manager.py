"""
Macro mode manager:
- Takes over number keys while active.
- Executes rich macro actions by layer/slot.
- Shows bottom dock overlay with icons and names.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import webbrowser
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import keyboard

from macro_overlay_qt import MacroDockManager
from context_aware import context_manager


class MacroManager:
    KEY_ORDER = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]

    def __init__(
        self,
        base_dir: Path,
        notify: Optional[Callable[[str, int], None]] = None,
        settings_getter: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        self.base_dir = base_dir
        self.notify = notify or (lambda _msg, _dur=1200: None)
        self.settings_getter = settings_getter or (lambda: {})
        self.overlay = MacroDockManager()
        self.active = False
        self.layers: List[Dict[str, Any]] = []
        self.current_layer = 0
        self.selected_slot = 0
        self.key_hotkeys: List[Any] = []
        self.layer_hotkeys: List[Any] = []

        self.config_path = self.base_dir / "macro_layers.json"
        self.counters_path = self.base_dir / "macro_counters.json"
        self.counters: Dict[str, int] = {}
        self._load_or_create_config()
        self._load_counters()
        self.overlay.start()

    def _load_counters(self):
        if not self.counters_path.exists():
            self.counters = {}
            return
        try:
            data = json.loads(self.counters_path.read_text(encoding="utf-8"))
            self.counters = data if isinstance(data, dict) else {}
        except Exception:
            self.counters = {}

    def _save_counters(self):
        try:
            self.counters_path.write_text(json.dumps(self.counters, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _next_counter(self, key: str) -> int:
        k = str(key or "default").strip().lower() or "default"
        value = int(self.counters.get(k, 0)) + 1
        self.counters[k] = value
        self._save_counters()
        return value

    def _get_clipboard_text(self) -> str:
        try:
            import win32clipboard  # type: ignore
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                    return str(win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT) or "")
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            pass
        return ""

    def _resolve_text_vars(self, value: str) -> str:
        text = str(value or "")
        ctx = context_manager.detector.get_current_context()
        window_title = str(getattr(ctx, "window_title", "") or "")
        active_exe = str(getattr(ctx, "process_name", "") or "")
        text = text.replace("{CLIPBOARD}", self._get_clipboard_text())
        text = text.replace("{WINDOW_TITLE}", window_title)
        text = text.replace("{ACTIVE_EXE}", active_exe)

        def _date_sub(match):
            fmt = match.group(1)
            return time.strftime(fmt if fmt else "%Y-%m-%d")

        text = re.sub(r"\{DATE(?::([^}]+))?\}", _date_sub, text)

        def _env_sub(match):
            key = str(match.group(1) or "").strip()
            return os.environ.get(key, "")

        text = re.sub(r"\{ENV:([^}]+)\}", _env_sub, text)

        def _counter_sub(match):
            key = str(match.group(1) or "default").strip()
            return str(self._next_counter(key))

        text = re.sub(r"\{COUNTER:([^}]+)\}", _counter_sub, text)
        return text

    def _match_window(self, process: str = "", title_regex: str = "") -> bool:
        ctx = context_manager.detector.get_current_context()
        if not ctx:
            return False
        proc_ok = True
        if process:
            proc_ok = bool(re.search(process, str(ctx.process_name or ""), re.IGNORECASE))
        title_ok = True
        if title_regex:
            title_ok = bool(re.search(title_regex, str(ctx.window_title or ""), re.IGNORECASE))
        return proc_ok and title_ok

    def _default_layers(self) -> Dict[str, Any]:
        def _slot(icon: str, name: str, action: Dict[str, Any]) -> Dict[str, Any]:
            return {"icon": icon, "name": name, "action": action}

        return {
            "layers": [
                {
                    "name": "Main",
                    "slots": [
                        _slot("🎙", "Discord Mute", {"type": "hotkey", "keys": "ctrl+shift+m"}),
                        _slot("🔇", "Discord Deafen", {"type": "hotkey", "keys": "ctrl+shift+d"}),
                        _slot("⏺", "OBS Record", {"type": "hotkey", "keys": "ctrl+shift+r"}),
                        _slot("📡", "OBS Stream", {"type": "hotkey", "keys": "ctrl+shift+s"}),
                        _slot("🎮", "Steam", {"type": "url", "url": "steam://open/library"}),
                        _slot("🌈", "SignalRGB", {"type": "url", "url": "signalrgb://"}),
                        _slot("🧪", "Launch Notepad", {"type": "shell", "command": "start notepad"}),
                        _slot("📝", "Paste Date", {"type": "sequence", "steps": [
                            {"type": "text", "text": "{DATE}"},
                            {"type": "hotkey", "keys": "enter"},
                        ]}),
                        _slot("🔒", "Lock PC", {"type": "hotkey", "keys": "windows+l"}),
                        _slot("⚙", "Open Settings", {"type": "shell", "command": "start ms-settings:"}),
                    ],
                },
                {
                    "name": "Media",
                    "slots": [
                        _slot("⏮", "Prev Track", {"type": "media", "command": "prev"}),
                        _slot("⏯", "Play/Pause", {"type": "media", "command": "play_pause"}),
                        _slot("⏭", "Next Track", {"type": "media", "command": "next"}),
                        _slot("🔉", "Vol Down", {"type": "hotkey", "keys": "volume down"}),
                        _slot("🔊", "Vol Up", {"type": "hotkey", "keys": "volume up"}),
                        _slot("🔕", "Mute", {"type": "hotkey", "keys": "volume mute"}),
                        _slot("🟩", "Clipboard 1", {"type": "text", "text": "Hello from Macro Mode"}),
                        _slot("🟦", "Clipboard 2", {"type": "text", "text": "Secondary text macro"}),
                        _slot("🟪", "Browser", {"type": "url", "url": "https://www.google.com"}),
                        _slot("🟥", "Terminal", {"type": "shell", "command": "start wt"}),
                    ],
                },
            ]
        }

    def _load_or_create_config(self):
        if not self.config_path.exists():
            self.config_path.write_text(json.dumps(self._default_layers(), indent=4), encoding="utf-8")
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception:
            data = self._default_layers()

        layers = data.get("layers", [])
        if not isinstance(layers, list) or not layers:
            layers = self._default_layers()["layers"]
        self.layers = layers
        self.current_layer = min(max(0, self.current_layer), len(self.layers) - 1)
        self.selected_slot = min(max(0, self.selected_slot), 9)

    def reload(self):
        self._load_or_create_config()
        if self.active:
            self._refresh_overlay()

    def get_config_path(self) -> Path:
        return self.config_path

    def _layer_slots(self) -> List[Dict[str, Any]]:
        if not self.layers:
            return []
        slots = self.layers[self.current_layer].get("slots", [])
        if not isinstance(slots, list):
            slots = []
        padded = list(slots[:10])
        while len(padded) < 10:
            padded.append({"name": f"Empty {len(padded)+1}", "icon": "⬡", "action": {"type": "noop"}})
        return padded

    def _overlay_payload(self) -> Dict[str, Any]:
        layer_name = str(self.layers[self.current_layer].get("name", f"Layer {self.current_layer+1}")) if self.layers else "Layer"
        return {
            "layer_name": layer_name,
            "layer_index": self.current_layer,
            "layer_count": len(self.layers),
            "selected_slot": self.selected_slot,
            "slots": self._layer_slots(),
        }

    def _refresh_overlay(self):
        if self.active:
            self.overlay.show(self._overlay_payload())

    def _register_number_overrides(self):
        self._unregister_number_overrides()
        for idx, key in enumerate(self.KEY_ORDER):
            hk = keyboard.add_hotkey(key, lambda i=idx: self.execute_slot(i), suppress=True, trigger_on_release=True)
            self.key_hotkeys.append(hk)

        # Shift+number: direct layer jump (1..0 => layer 1..10).
        for idx, key in enumerate(self.KEY_ORDER):
            hk = keyboard.add_hotkey(f"shift+{key}", lambda i=idx: self.set_layer(i), suppress=True, trigger_on_release=True)
            self.layer_hotkeys.append(hk)

    def _unregister_number_overrides(self):
        for hk in self.key_hotkeys:
            try:
                keyboard.remove_hotkey(hk)
            except Exception:
                pass
        self.key_hotkeys = []
        for hk in self.layer_hotkeys:
            try:
                keyboard.remove_hotkey(hk)
            except Exception:
                pass
        self.layer_hotkeys = []

    def activate(self):
        if self.active:
            return
        self._load_or_create_config()
        self.active = True
        self._register_number_overrides()
        self.selected_slot = 0
        self._refresh_overlay()

    def deactivate(self):
        if not self.active:
            return
        self.active = False
        self._unregister_number_overrides()
        self.overlay.hide()

    def toggle(self) -> bool:
        if self.active:
            self.deactivate()
            return False
        self.activate()
        return True

    def set_layer(self, layer_index_zero_based: int):
        if not self.layers:
            return
        idx = max(0, min(int(layer_index_zero_based), len(self.layers) - 1))
        self.current_layer = idx
        self.selected_slot = 0
        self._refresh_overlay()
        self.notify(f"Layer: {self.layers[self.current_layer].get('name', self.current_layer + 1)}", 1000)

    def cycle_layer(self, delta: int):
        if not self.layers:
            return
        self.current_layer = (self.current_layer + int(delta)) % len(self.layers)
        self.selected_slot = 0
        self._refresh_overlay()
        self.notify(f"Layer: {self.layers[self.current_layer].get('name', self.current_layer + 1)}", 1000)

    def rotate_selection(self, clockwise: bool, steps: int = 1):
        if not self.active:
            return
        count = len(self.KEY_ORDER)
        step = max(1, int(steps))
        delta = step if clockwise else -step
        self.selected_slot = (self.selected_slot + delta) % count
        self._refresh_overlay()

    def execute_selected(self):
        if not self.active:
            return
        self.execute_slot(self.selected_slot)

    def execute_slot(self, slot_index: int):
        if not self.active:
            return
        slots = self._layer_slots()
        if slot_index < 0 or slot_index >= len(slots):
            return
        self.selected_slot = slot_index
        self._refresh_overlay()
        slot = slots[slot_index]
        name = str(slot.get("name", f"Macro {slot_index+1}"))
        action = slot.get("action", {})
        ok = self._run_action(action)
        self.notify(f"{'Ran' if ok else 'Failed'}: {name}", 1200 if ok else 1800)

    def _run_action(self, action: Any) -> bool:
        if not isinstance(action, dict):
            return False
        action_type = str(action.get("type", "noop")).strip().lower()

        if action_type == "noop":
            return True
        if action_type == "hotkey":
            keys = str(action.get("keys", "")).strip()
            if not keys:
                return False
            keyboard.send(keys)
            return True
        if action_type == "text":
            text = self._resolve_text_vars(str(action.get("text", "")))
            keyboard.write(text)
            return True
        if action_type == "shell":
            cmd = self._resolve_text_vars(str(action.get("command", "")).strip())
            if not cmd:
                return False
            subprocess.Popen(["cmd", "/c", cmd], shell=False)
            return True
        if action_type == "url":
            url = self._resolve_text_vars(str(action.get("url", "")).strip())
            if not url:
                return False
            webbrowser.open(url)
            return True
        if action_type == "delay":
            ms = max(0, int(action.get("ms", 0)))
            time.sleep(ms / 1000.0)
            return True
        if action_type == "media":
            cmd = str(action.get("command", "")).strip().lower()
            mapping = {
                "play_pause": "play/pause media",
                "next": "next track",
                "prev": "previous track",
            }
            key = mapping.get(cmd)
            if not key:
                return False
            keyboard.send(key)
            return True
        if action_type == "sequence":
            steps = action.get("steps", [])
            if not isinstance(steps, list):
                return False
            for step in steps:
                if not self._run_action(step):
                    return False
            return True
        if action_type == "repeat":
            count = max(0, int(action.get("count", 0)))
            steps = action.get("actions", [])
            if not isinstance(steps, list):
                return False
            for _ in range(count):
                for step in steps:
                    if not self._run_action(step):
                        return False
            return True
        if action_type == "if_window":
            process = str(action.get("process", "")).strip()
            title_regex = str(action.get("title_regex", "")).strip()
            matched = self._match_window(process=process, title_regex=title_regex)
            branch = action.get("then" if matched else "else", [])
            if not isinstance(branch, list):
                return False
            for step in branch:
                if not self._run_action(step):
                    return False
            return True
        if action_type == "if_setting":
            key = str(action.get("key", "")).strip()
            expected = action.get("value")
            settings = self.settings_getter() if callable(self.settings_getter) else {}
            actual = settings.get(key) if isinstance(settings, dict) else None
            matched = actual == expected
            branch = action.get("then" if matched else "else", [])
            if not isinstance(branch, list):
                return False
            for step in branch:
                if not self._run_action(step):
                    return False
            return True
        if action_type == "ahk":
            script = self._resolve_text_vars(str(action.get("script", "")).strip())
            if not script:
                return False
            try:
                temp_path = self.base_dir / "_macro_temp.ahk"
                temp_path.write_text(script, encoding="utf-8")
                subprocess.Popen(["cmd", "/c", "start", "", "autohotkey", str(temp_path)], shell=False)
                return True
            except Exception:
                return False
        return False
