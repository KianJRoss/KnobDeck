"""
KnobDeck - Qt Main Application

Properly restructured with Qt on main thread and HID in worker thread.
"""

import sys
import logging
import json
import os
import tempfile
import ctypes
import importlib
import pkgutil
import re
import time
from typing import Optional, List, Dict, Any
from pathlib import Path
import subprocess

from PyQt6.QtCore import QObject, pyqtSlot, QTimer, QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QGuiApplication, QIcon

# Import our modules
from menu_system import MenuStateMachine, MenuMode
from mode_handlers import create_handlers
from windows_api import SystemAPI
from voicemeeter_api import VoicemeeterController
from tray_icon import TrayIcon
from hid_reader_thread import HIDReaderThread
from overlay_qt import EnhancedUIManager
from signalrgb_control import SignalRGBController
from device_profiles import (
    list_profiles as list_keyboard_profiles,
    get_profile as get_keyboard_profile,
    detect_connected_profile,
)
from settings_dialog import SettingsDialog
from context_aware import context_manager
from macro_manager import MacroManager
from macro_editor_dialog import MacroEditorDialog
from context_aware import AppContext

# ============================================================================
# LOGGING SETUP
# ============================================================================

log_handlers = []

# Always log to file
log_dir = Path(__file__).parent / 'logs'
log_dir.mkdir(exist_ok=True)
log_file = log_dir / 'knobdeck_app.log'

file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
log_handlers.append(file_handler)

# Also log to console if running with python.exe
if sys.executable.endswith('python.exe'):
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    log_handlers.append(console_handler)

logging.basicConfig(
    level=logging.INFO,
    handlers=log_handlers
)

logger = logging.getLogger(__name__)
_instance_lock_file = None
_instance_mutex_handle = None

# ============================================================================
# PLUGIN MANAGER
# ============================================================================

class PluginManager:
    """Discovers and loads plugins from plugins/ directory"""

    def __init__(self):
        self.plugins = []
        self.plugin_handlers = {}
        self.loaded_paths = []
        self.plugin_meta: Dict[str, Dict[str, Any]] = {}
        self.failed_plugins: Dict[str, str] = {}
        self._plugin_file_mtimes: Dict[str, float] = {}

    def _read_manifest(self, plugin_dir: Path, name: str, ispkg: bool) -> Dict[str, Any]:
        """Read optional plugin manifest from sidecar or package folder."""
        candidates = [plugin_dir / f"{name}.plugin.json"]
        if ispkg:
            candidates.append(plugin_dir / name / "plugin.json")
        for path in candidates:
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    data["_manifest_path"] = str(path)
                    return data
            except Exception as e:
                logger.warning(f"Failed to parse manifest for {name}: {e}")
        return {}

    def _load_plugins_from_dir(
        self,
        plugin_dir: Path,
        state_machine,
        disabled_plugin_names: Optional[set] = None,
        plugin_settings: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        if not plugin_dir.exists():
            return

        sys.path.insert(0, str(plugin_dir))
        self.loaded_paths.append(str(plugin_dir))

        for finder, name, ispkg in pkgutil.iter_modules([str(plugin_dir)]):
            if disabled_plugin_names and name in disabled_plugin_names:
                logger.info(f"Skipping plugin by settings: {name}")
                continue
            try:
                logger.info(f"Loading plugin: {name} ({plugin_dir})")
                module = importlib.import_module(name)
                try:
                    mod_file = Path(getattr(module, "__file__", "")).resolve()
                    if mod_file.exists():
                        self._plugin_file_mtimes[str(mod_file)] = mod_file.stat().st_mtime
                except Exception:
                    pass
                manifest = self._read_manifest(plugin_dir, name, ispkg)
                self.plugin_meta[name] = {
                    "name": str(manifest.get("name", name)),
                    "module": name,
                    "version": str(manifest.get("version", "")),
                    "author": str(manifest.get("author", "")),
                    "description": str(manifest.get("description", "")),
                    "settings_schema": manifest.get("settings_schema", []),
                    "manifest_path": manifest.get("_manifest_path", ""),
                    "source_dir": str(plugin_dir),
                }
                try:
                    man_path = self.plugin_meta[name].get("manifest_path", "")
                    if man_path:
                        mp = Path(str(man_path))
                        if mp.exists():
                            self._plugin_file_mtimes[str(mp.resolve())] = mp.stat().st_mtime
                except Exception:
                    pass

                if hasattr(module, 'configure'):
                    psettings = {}
                    if isinstance(plugin_settings, dict):
                        raw = plugin_settings.get(name, {})
                        if isinstance(raw, dict):
                            psettings = raw
                    try:
                        module.configure(psettings)
                    except Exception as e:
                        logger.warning(f"Plugin configure failed for {name}: {e}")

                if hasattr(module, 'get_commands'):
                    commands = module.get_commands()
                    for cmd in commands:
                        state_machine.commands.register(
                            cmd['name'],
                            cmd['description'],
                            cmd['callback']
                        )
                        logger.info(f"  + Registered command: {cmd['name']}")

                if hasattr(module, 'get_mode_handlers'):
                    handlers = module.get_mode_handlers(state_machine)
                    self.plugin_handlers.update(handlers)
                    for mode_name in handlers.keys():
                        logger.info(f"  + Registered plugin mode handler: {mode_name}")

                self.plugins.append(module)
            except Exception as e:
                logger.error(f"Failed to load plugin {name}: {e}")
                self.failed_plugins[name] = str(e)

    def load_plugins(
        self,
        state_machine,
        plugin_dirs: Optional[List[str]] = None,
        disabled_plugin_names: Optional[set] = None,
        plugin_settings: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        """Load all plugins from built-in and custom directories."""
        built_in = Path(__file__).parent / 'plugins'
        self._load_plugins_from_dir(
            built_in,
            state_machine,
            disabled_plugin_names=disabled_plugin_names,
            plugin_settings=plugin_settings,
        )

        for rel_dir in plugin_dirs or []:
            plugin_dir = (Path(__file__).parent / str(rel_dir)).resolve()
            if plugin_dir == built_in.resolve():
                continue
            self._load_plugins_from_dir(
                plugin_dir,
                state_machine,
                disabled_plugin_names=disabled_plugin_names,
                plugin_settings=plugin_settings,
            )

    def has_plugin_file_changes(self) -> bool:
        """Check known plugin/module/manifest files for mtime changes."""
        changed = False
        for path_str, old_mtime in list(self._plugin_file_mtimes.items()):
            try:
                p = Path(path_str)
                if not p.exists():
                    changed = True
                    continue
                new_mtime = p.stat().st_mtime
                if new_mtime != old_mtime:
                    changed = True
                    self._plugin_file_mtimes[path_str] = new_mtime
            except Exception:
                changed = True
        return changed


# ============================================================================
# KEYCHRON APPLICATION (QObject for signals/slots)
# ============================================================================

class KeychronApp(QObject):
    """Main application - integrates HID, state machine, and UI using Qt"""
    open_settings_signal = pyqtSignal()

    def __init__(self, config, app: QApplication):
        super().__init__()

        self.config = config
        self.app = app
        self.app_settings: Dict[str, Any] = self.config.setdefault('app_settings', {})
        self.keyboard_profile_id: str = str(self.config.get("keyboard_profile_id", "default_qmk_knob"))
        self.open_settings_signal.connect(self._open_settings_window_slot)

        self._apply_keyboard_profile(self.keyboard_profile_id, persist=False)

        # Components
        self.api = SystemAPI()
        self.vm = VoicemeeterController()
        self.state_machine = MenuStateMachine()
        self.plugin_manager = PluginManager()
        self.signalrgb = SignalRGBController(
            vendor_id=config['hid']['vendor_id'],
            product_id=config['hid']['product_id'],
            usage_page=config['hid']['usage_page'],
            usage=config['hid']['usage']
        )
        self.macro_manager = MacroManager(
            base_dir=Path(__file__).parent,
            notify=lambda msg, dur=1200: self._show_notification(msg, dur),
            settings_getter=self.get_runtime_settings,
        )

        # UI - Qt overlay
        self.ui = EnhancedUIManager(theme=config['ui_theme'])

        # HID Reader Thread
        self.hid_reader: Optional[HIDReaderThread] = None

        # Tray icon
        self.tray_icon = TrayIcon(self)
        self.settings_dialog: Optional[SettingsDialog] = None
        self.macro_editor_dialog: Optional[MacroEditorDialog] = None
        self._all_commands: Dict[str, Any] = {}

        # State tracking
        self.is_pressed = False
        self.long_press_active = False
        self.was_rotated_while_pressed = False
        self.ignore_next_release = False
        self.last_command_index = 0
        self._hotkeys_registered = False
        self.timeout_timer = None # Added for timeout check
        self.volume_hide_timer = None # Auto-hide timer for quick volume
        self.click_confirm_timer = None
        self.pending_press_mode = None
        self.pending_macro_execute = False
        self.pending_macro_toggle = False
        self.hidden_tap_timer = None
        self.macro_toggle_timer = None
        self.hidden_tap_count = 0
        self.last_hidden_tap_ms = 0
        self.last_activity_time = 0  # Track last activity for stuck press detection
        self.quick_volume_hide_ms = int(self.app_settings.get('quick_volume_hide_ms', 800))
        self.profile_timer: Optional[QTimer] = None
        self.plugin_watch_timer: Optional[QTimer] = None
        self._active_profile_name = str(self.app_settings.get('active_profile_name', 'Default'))
        self.recent_actions: List[Dict[str, Any]] = []
        self._last_plugin_change_notice_ms = 0

    def _apply_keyboard_profile(self, profile_id: str, persist: bool = True) -> bool:
        """Apply keyboard profile HID values into runtime config."""
        profile = get_keyboard_profile(profile_id)
        if not profile:
            return False
        self.keyboard_profile_id = profile.id
        self.config["keyboard_profile_id"] = profile.id
        self.config["hid"] = {
            "vendor_id": int(profile.vendor_id),
            "product_id": int(profile.product_id),
            "usage_page": int(profile.usage_page),
            "usage": int(profile.usage),
        }
        if persist:
            self._save_config()
        return True

    def get_keyboard_profile_catalog(self) -> List[Dict[str, Any]]:
        """Return keyboard profile catalog for settings/docs UI."""
        return [p.as_dict() for p in list_keyboard_profiles()]

    def detect_and_apply_keyboard_profile(self) -> Optional[Dict[str, Any]]:
        """Auto-detect connected keyboard profile and apply config if matched."""
        detected = detect_connected_profile()
        if not detected:
            return None
        applied = self._apply_keyboard_profile(detected.id, persist=True)
        if not applied:
            return None
        try:
            self.signalrgb = SignalRGBController(
                vendor_id=self.config["hid"]["vendor_id"],
                product_id=self.config["hid"]["product_id"],
                usage_page=self.config["hid"]["usage_page"],
                usage=self.config["hid"]["usage"],
            )
            self.state_machine.signalrgb = self.signalrgb
        except Exception as e:
            logger.warning(f"Failed to reinitialize SignalRGB after profile detect: {e}")
        return detected.as_dict()

    def set_keyboard_profile(self, profile_id: str) -> bool:
        """Set keyboard profile manually from settings UI."""
        applied = self._apply_keyboard_profile(profile_id, persist=True)
        if not applied:
            return False
        try:
            self.signalrgb = SignalRGBController(
                vendor_id=self.config["hid"]["vendor_id"],
                product_id=self.config["hid"]["product_id"],
                usage_page=self.config["hid"]["usage_page"],
                usage=self.config["hid"]["usage"],
            )
            self.state_machine.signalrgb = self.signalrgb
            self.state_machine.update_display()
        except Exception as e:
            logger.warning(f"Failed to reinitialize SignalRGB after profile change: {e}")
        return True

    def get_runtime_settings(self) -> Dict[str, Any]:
        """Return runtime settings for tray UI."""
        defaults = {
            'menu_timeout_ms': 3000,
            'double_click_ms': 300,
            'volume_step': 2,
            'quick_volume_hide_ms': 800,
            'triple_click_settings_enabled': True,
            'triple_click_window_ms': 700,
            'side_label_max_chars': 18,
            'lighting_backend': 'signalrgb',
            'macro_mode_enabled': True,
            'enable_voicemeeter_integration': True,
            'enable_plugin_integrations': True,
            'enable_context_commands': True,
            'plugin_hot_reload_enabled': True,
            'auto_profile_switch_enabled': True,
            'show_status_indicator': True,
            'show_onboarding_on_start': True,
            'onboarding_completed': False,
            'active_profile_name': 'Default',
            'profiles': [
                {
                    'name': 'Default',
                    'priority': 0,
                    'theme': '',
                    'command_order': [],
                    'command_hidden': [],
                    'macro_layer': None,
                    'auto_switch': {},
                }
            ],
            'notifications_enabled': True,
            'submenu_timeout_enabled': True,
            'restore_voicemeeter_on_start': False,
            'voicemeeter_profile': {},
            'plugin_dirs': ['custom_plugins'],
            'plugin_settings': {},
            'disabled_plugins_auto': [],
            'command_order': [],
            'command_hidden': [],
            'mode_timeout_ms': {
                'VOICEMEETER_MENU': 5000,
                'VM_MIC': 5000,
                'VM_MAIN_ROUTING': 5000,
                'VM_MUSIC_GAIN': 5000,
                'VM_MUSIC_ROUTING': 5000,
                'VM_COMM_GAIN': 5000,
                'VM_COMM_ROUTING': 5000,
                'LIGHTING_MENU': 5000,
                'LIGHTING_EFFECTS': 8000,
            },
        }
        merged = defaults.copy()
        merged.update(self.app_settings)
        return merged

    def _normalize_profiles(self, raw_profiles: Any) -> List[Dict[str, Any]]:
        """Normalize profile list from settings/import payloads."""
        if not isinstance(raw_profiles, list):
            raw_profiles = []
        profiles: List[Dict[str, Any]] = []
        for item in raw_profiles:
            if not isinstance(item, dict):
                continue
            auto = item.get("auto_switch", {})
            if not isinstance(auto, dict):
                auto = {}
            profile = {
                "name": self._clean_profile_name(item.get("name", "Default")),
                "priority": int(item.get("priority", 0)),
                "theme": str(item.get("theme", "")).strip(),
                "command_order": item.get("command_order", []) if isinstance(item.get("command_order", []), list) else [],
                "command_hidden": item.get("command_hidden", []) if isinstance(item.get("command_hidden", []), list) else [],
                "macro_layer": item.get("macro_layer"),
                "auto_switch": {
                    "process_regex": str(auto.get("process_regex", "")).strip(),
                    "title_regex": str(auto.get("title_regex", "")).strip(),
                    "exclude_processes": auto.get("exclude_processes", []) if isinstance(auto.get("exclude_processes", []), list) else [],
                },
            }
            profiles.append(profile)
        if not profiles:
            profiles = [{
                "name": "Default",
                "priority": 0,
                "theme": "",
                "command_order": [],
                "command_hidden": [],
                "macro_layer": None,
                "auto_switch": {},
            }]
        if not any(self._clean_profile_name(p.get("name")) == "Default" for p in profiles):
            profiles.insert(0, {
                "name": "Default",
                "priority": 0,
                "theme": "",
                "command_order": [],
                "command_hidden": [],
                "macro_layer": None,
                "auto_switch": {},
            })
        return profiles

    def _mode_accent_override(self, mode: MenuMode) -> Dict[str, str]:
        """Color accents by mode for stronger visual identity."""
        accent_map = {
            MenuMode.VOLUME: '#3D8AFF',
            MenuMode.VOLUME_MIXER: '#3D8AFF',
            MenuMode.MEDIA: '#29B36B',
            MenuMode.VOICEMEETER_MENU: '#F28A2A',
            MenuMode.VM_MIC: '#F28A2A',
            MenuMode.VM_MAIN_ROUTING: '#F28A2A',
            MenuMode.VM_MUSIC_GAIN: '#F28A2A',
            MenuMode.VM_MUSIC_ROUTING: '#F28A2A',
            MenuMode.VM_COMM_GAIN: '#F28A2A',
            MenuMode.VM_COMM_ROUTING: '#F28A2A',
            MenuMode.LIGHTING_MENU: '#9B59FF',
            MenuMode.LIGHTING_EFFECTS: '#9B59FF',
            MenuMode.WINDOW_MENU: '#4DB6AC',
            MenuMode.WINDOW_CYCLE: '#4DB6AC',
            MenuMode.WINDOW_SNAP: '#4DB6AC',
            MenuMode.CONTEXT_MENU: '#E67E22',
            MenuMode.INTEGRATIONS_MENU: '#58A6FF',
            MenuMode.INTEGRATION_DISCORD: '#5865F2',
            MenuMode.INTEGRATION_OBS: '#E0465E',
            MenuMode.INTEGRATION_STEAM: '#66C0F4',
            MenuMode.INTEGRATION_SIGNALRGB: '#A53BFF',
        }
        accent = accent_map.get(mode)
        if not accent:
            return {}
        return {
            'accent': accent,
            'accent_glow': accent,
            'glow': accent,
            'segment_active': accent,
            'progress_fill': accent,
        }

    def _build_breadcrumb(self, display: Dict[str, Any]) -> str:
        """Build concise navigation breadcrumb subtitle."""
        mode = self.state_machine.state.menu_mode
        if mode == MenuMode.NORMAL:
            return str(display.get('subtitle', ''))

        title = str(display.get('title', '')).strip()
        original_sub = str(display.get('subtitle', '')).strip()
        path = f"Main > {title}" if title else f"Main > {mode.name.replace('_', ' ').title()}"
        if original_sub and original_sub != title:
            return f"{path} | {original_sub}"
        return path

    def _clean_profile_name(self, name: str) -> str:
        return str(name or "Default").strip() or "Default"

    def _get_profiles(self) -> List[Dict[str, Any]]:
        profiles = self.get_runtime_settings().get('profiles', [])
        if not isinstance(profiles, list):
            return [{'name': 'Default', 'priority': 0, 'auto_switch': {}}]
        cleaned = []
        for p in profiles:
            if not isinstance(p, dict):
                continue
            item = dict(p)
            item['name'] = self._clean_profile_name(item.get('name', 'Default'))
            item['priority'] = int(item.get('priority', 0))
            if not isinstance(item.get('auto_switch'), dict):
                item['auto_switch'] = {}
            cleaned.append(item)
        if not cleaned:
            cleaned.append({'name': 'Default', 'priority': 0, 'auto_switch': {}})
        return cleaned

    def _profile_matches(self, profile: Dict[str, Any], ctx: Optional[AppContext]) -> bool:
        auto = profile.get('auto_switch', {})
        if not isinstance(auto, dict):
            return False
        if not ctx:
            return False
        process_pat = str(auto.get('process_regex', '')).strip()
        title_pat = str(auto.get('title_regex', '')).strip()
        exclude = auto.get('exclude_processes', [])
        exclude_set = {str(x).lower() for x in exclude} if isinstance(exclude, list) else set()
        proc = str(ctx.process_name or '').lower()
        title = str(ctx.window_title or '')
        if proc in exclude_set:
            return False
        proc_ok = True if not process_pat else bool(re.search(process_pat, proc, re.IGNORECASE))
        title_ok = True if not title_pat else bool(re.search(title_pat, title, re.IGNORECASE))
        return proc_ok and title_ok

    def _resolve_profile_for_context(self, ctx: Optional[AppContext]) -> Dict[str, Any]:
        profiles = self._get_profiles()
        matches = [p for p in profiles if self._profile_matches(p, ctx)]
        if matches:
            matches.sort(key=lambda p: int(p.get('priority', 0)), reverse=True)
            return matches[0]
        for p in profiles:
            if self._clean_profile_name(p.get('name')) == 'Default':
                return p
        return profiles[0]

    def _apply_profile(self, profile: Dict[str, Any]):
        name = self._clean_profile_name(profile.get('name', 'Default'))
        if name == self._active_profile_name:
            return

        self._active_profile_name = name
        self.app_settings['active_profile_name'] = name

        theme_name = str(profile.get('theme', '')).strip()
        if theme_name:
            self.set_theme(theme_name)

        order = profile.get('command_order')
        hidden = profile.get('command_hidden')
        if isinstance(order, list) and isinstance(hidden, list):
            self._apply_command_layout(order=order, hidden=hidden, persist=False)

        macro_layer = profile.get('macro_layer')
        if isinstance(macro_layer, int):
            try:
                self.macro_manager.set_layer(int(macro_layer))
            except Exception:
                pass

        self._save_config()
        self._show_notification(f"Profile: {name}", 1000)
        self.state_machine.update_display()
        self._update_status_indicator()

    def _update_status_indicator(self):
        if not self.get_runtime_settings().get('show_status_indicator', True):
            if hasattr(self.ui, 'set_status'):
                self.ui.set_status('', visible=False)
            return
        mode_name = self.state_machine.state.menu_mode.name.replace('_', ' ').title()
        text = f"{self._active_profile_name} | {mode_name}"
        if hasattr(self.ui, 'set_status'):
            self.ui.set_status(text, visible=True)

    def _record_recent_action(self, name: str, callback: Optional[Any] = None):
        """Track recent actions for quick rerun mode."""
        entry = {
            "name": str(name or "").strip() or "Action",
            "callback": callback,
            "ts": int(time.time()),
        }
        self.recent_actions.insert(0, entry)
        self.recent_actions = self.recent_actions[:10]

    def get_recent_actions(self) -> List[Dict[str, Any]]:
        """Provide recent actions list to mode handlers."""
        return [dict(item) for item in self.recent_actions if callable(item.get("callback"))]

    def get_health_status(self) -> Dict[str, Any]:
        """Return runtime health checks for diagnostics UI."""
        hid_status = bool(self._hotkeys_registered)
        vm_status = bool(self.vm and self.vm.is_available())
        tray_status = bool(self.tray_icon and getattr(self.tray_icon, "icon", None))
        return {
            "hotkeys_registered": hid_status,
            "tray_visible": tray_status,
            "voicemeeter_connected": vm_status,
            "signalrgb_enabled": self._is_signalrgb_enabled(),
            "active_profile": self._active_profile_name,
            "plugin_count": len(self.plugin_manager.plugins),
            "plugin_failed": dict(self.plugin_manager.failed_plugins),
        }

    def open_onboarding_tutorial(self):
        """Open onboarding/tutorial dialog."""
        try:
            from onboarding_dialog import OnboardingDialog
            dlg = OnboardingDialog(parent=self.settings_dialog if self.settings_dialog and self.settings_dialog.isVisible() else None)
            if dlg.exec():
                self.app_settings["onboarding_completed"] = True
                self._save_config()
        except Exception as e:
            logger.error(f"Failed to open onboarding tutorial: {e}")

    def export_settings_bundle(self, output_path: str) -> bool:
        """Export current app settings for backup/transfer."""
        try:
            payload = {
                "version": 1,
                "exported_at_epoch": int(time.time()),
                "ui_theme": str(self.config.get("ui_theme", "DARK")),
                "app_settings": self.get_runtime_settings(),
            }
            out = Path(str(output_path))
            out.write_text(json.dumps(payload, indent=4), encoding="utf-8")
            return True
        except Exception as e:
            logger.error(f"Export settings failed: {e}")
            return False

    def import_settings_bundle(self, input_path: str) -> bool:
        """Import settings from backup JSON and apply immediately."""
        try:
            data = json.loads(Path(str(input_path)).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return False
            imported = data.get("app_settings", {})
            if not isinstance(imported, dict):
                return False

            self.app_settings.update(imported)
            self.app_settings["profiles"] = self._normalize_profiles(self.app_settings.get("profiles", []))

            theme = str(data.get("ui_theme", "")).strip()
            if theme:
                self.set_theme(theme)

            self.quick_volume_hide_ms = int(self.app_settings.get("quick_volume_hide_ms", 800))
            self.state_machine.apply_settings(self.get_runtime_settings())
            self._reconfigure_voicemeeter_runtime()
            self._rebuild_runtime_bindings()
            self._reload_builtin_handlers()
            self._update_status_indicator()
            self._save_config()
            self.state_machine.update_display()
            return True
        except Exception as e:
            logger.error(f"Import settings failed: {e}")
            return False

    def clear_auto_disabled_plugins(self):
        """Clear plugin crash-guard auto-disabled list."""
        self.app_settings["disabled_plugins_auto"] = []
        self._save_config()
        self._rebuild_runtime_bindings()

    def _check_plugin_hot_reload(self):
        """Detect plugin file changes and hot-reload bindings."""
        if not self.get_runtime_settings().get("plugin_hot_reload_enabled", True):
            return
        if not self._is_plugins_enabled():
            return
        try:
            if self.plugin_manager.has_plugin_file_changes():
                self._rebuild_runtime_bindings()
                now = int(time.time() * 1000)
                if now - self._last_plugin_change_notice_ms > 2000:
                    self._show_notification("Plugins reloaded", 1000)
                    self._last_plugin_change_notice_ms = now
        except Exception as e:
            logger.debug(f"Plugin hot-reload check failed: {e}")

    def _is_signalrgb_enabled(self) -> bool:
        backend = str(self.get_runtime_settings().get('lighting_backend', 'signalrgb')).strip().lower()
        return backend == 'signalrgb'

    def _is_voicemeeter_enabled(self) -> bool:
        return bool(self.get_runtime_settings().get('enable_voicemeeter_integration', True))

    def _is_plugins_enabled(self) -> bool:
        return bool(self.get_runtime_settings().get('enable_plugin_integrations', True))

    def _is_context_enabled(self) -> bool:
        return bool(self.get_runtime_settings().get('enable_context_commands', True))

    def update_setting(self, key: str, value: Any):
        """Update one runtime setting and apply immediately where possible."""
        settings = self.get_runtime_settings()
        settings[key] = value
        self.app_settings.update(settings)

        self.quick_volume_hide_ms = int(settings.get('quick_volume_hide_ms', 800))
        self.state_machine.apply_settings(settings)
        if hasattr(self.ui, 'set_side_label_max_chars'):
            self.ui.set_side_label_max_chars(int(settings.get('side_label_max_chars', 18)))
        if key == 'show_status_indicator':
            self._update_status_indicator()
        if key == 'macro_mode_enabled' and not bool(value):
            self.macro_manager.deactivate()
        if key in ('lighting_backend', 'enable_voicemeeter_integration', 'enable_plugin_integrations', 'enable_context_commands'):
            self._apply_command_layout(persist=False)
        self._save_config()

    def get_voicemeeter_profile(self) -> Dict[str, Any]:
        """Return persisted or live Voicemeeter mapping profile."""
        profile = self.app_settings.get('voicemeeter_profile')
        if isinstance(profile, dict) and profile:
            return profile
        if self.vm and getattr(self.vm, 'config', None):
            return self.vm.config.as_dict()
        return {}

    def get_command_layout(self) -> Dict[str, Any]:
        """Return command ordering/visibility metadata for settings UI."""
        names = list(self._all_commands.keys())
        descriptions = {name: self._all_commands[name].description for name in names if name in self._all_commands}

        configured_order = [name for name in self.app_settings.get('command_order', []) if name in self._all_commands]
        order = configured_order + [name for name in names if name not in configured_order]
        hidden = [name for name in self.app_settings.get('command_hidden', []) if name in self._all_commands]

        return {
            'order': order,
            'hidden': hidden,
            'descriptions': descriptions,
        }

    def get_plugin_catalog(self) -> List[Dict[str, Any]]:
        """Return loaded plugin metadata plus effective settings."""
        settings_map = self.get_runtime_settings().get('plugin_settings', {})
        if not isinstance(settings_map, dict):
            settings_map = {}
        items: List[Dict[str, Any]] = []
        for module_name, meta in (self.plugin_manager.plugin_meta or {}).items():
            schema = meta.get("settings_schema", [])
            values = settings_map.get(module_name, {})
            if not isinstance(values, dict):
                values = {}
            items.append({
                "module": module_name,
                "name": str(meta.get("name", module_name)),
                "version": str(meta.get("version", "")),
                "author": str(meta.get("author", "")),
                "description": str(meta.get("description", "")),
                "manifest_path": str(meta.get("manifest_path", "")),
                "settings_schema": schema if isinstance(schema, list) else [],
                "settings_values": values,
            })
        items.sort(key=lambda x: x["name"].lower())
        return items

    def _apply_command_layout(self, order: Optional[List[str]] = None, hidden: Optional[List[str]] = None, persist: bool = False) -> bool:
        """Apply command ordering and visibility to wheel commands."""
        if not self._all_commands:
            return False

        all_names = list(self._all_commands.keys())
        order = order if order is not None else list(self.app_settings.get('command_order', []))
        hidden = hidden if hidden is not None else list(self.app_settings.get('command_hidden', []))

        normalized_order = [name for name in order if name in self._all_commands]
        normalized_order += [name for name in all_names if name not in normalized_order]
        hidden_set = {name for name in hidden if name in self._all_commands}
        forced_hidden = set()

        # Backend-driven visibility: hide SignalRGB lighting command when VIA/onboard is selected.
        if not self._is_signalrgb_enabled():
            forced_hidden.add('Lighting')

        visible_names = [name for name in normalized_order if name not in hidden_set and name not in forced_hidden]
        if not visible_names:
            return False

        self.state_machine.commands.commands = [self._all_commands[name] for name in visible_names]
        if self.state_machine.state.current_command >= self.state_machine.commands.count():
            self.state_machine.state.current_command = 0
            self.last_command_index = 0

        if persist:
            self.app_settings['command_order'] = list(normalized_order)
            self.app_settings['command_hidden'] = sorted(hidden_set)
            self._save_config()

        return True

    def apply_settings_payload(self, payload: Dict[str, Any]):
        """Apply a full settings payload from the settings dialog."""
        prev_vm_enabled = self._is_voicemeeter_enabled()
        prev_plugins_enabled = self._is_plugins_enabled()
        prev_context_enabled = self._is_context_enabled()

        settings = payload.get('settings', {})
        for key, value in settings.items():
            self.update_setting(key, value)

        theme = payload.get('theme')
        if isinstance(theme, str) and theme:
            self.set_theme(theme)

        kb_profile_id = payload.get("keyboard_profile_id")
        if isinstance(kb_profile_id, str) and kb_profile_id.strip():
            self.set_keyboard_profile(kb_profile_id.strip())

        order = payload.get('command_order', [])
        hidden = payload.get('command_hidden', [])
        if isinstance(order, list) and isinstance(hidden, list):
            if not self._apply_command_layout(order, hidden, persist=True):
                self._show_notification("Invalid command layout (need at least one visible command)", 1800)

        vm_profile = payload.get('voicemeeter_profile')
        if isinstance(vm_profile, dict):
            self.app_settings['voicemeeter_profile'] = vm_profile
            try:
                self.vm.apply_profile(vm_profile)
            except Exception as e:
                logger.warning(f"Failed to apply Voicemeeter profile: {e}")
            self._save_config()

        plugin_settings = payload.get('plugin_settings')
        if isinstance(plugin_settings, dict):
            self.app_settings['plugin_settings'] = plugin_settings
            self._save_config()

        profiles = payload.get('profiles')
        if isinstance(profiles, list):
            self.app_settings['profiles'] = self._normalize_profiles(profiles)
            self._save_config()

        auto_disabled = payload.get('disabled_plugins_auto')
        if isinstance(auto_disabled, list):
            self.app_settings['disabled_plugins_auto'] = [str(x) for x in auto_disabled]
            self._save_config()

        self._reconfigure_voicemeeter_runtime()
        self._reload_builtin_handlers()

        if (
            prev_vm_enabled != self._is_voicemeeter_enabled()
            or prev_plugins_enabled != self._is_plugins_enabled()
            or prev_context_enabled != self._is_context_enabled()
            or isinstance(vm_profile, dict)
            or isinstance(plugin_settings, dict)
        ):
            self._rebuild_runtime_bindings()

        self.state_machine.update_display()
        self._show_notification("Settings saved", 1200)

    def open_settings_window(self):
        """Open settings dialog on the Qt main thread."""
        self.open_settings_signal.emit()

    @pyqtSlot()
    def _open_settings_window_slot(self):
        """Open settings UI in the app's Qt thread."""
        try:
            self.macro_manager.deactivate()
            if hasattr(self.ui, "hide_menu"):
                self.ui.hide_menu()
            if hasattr(self.ui, "ensure_cursor_visible"):
                self.ui.ensure_cursor_visible()
            if self.settings_dialog is None or not self.settings_dialog.isVisible():
                self.settings_dialog = SettingsDialog(self)
            self.settings_dialog.show()
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            logger.info("Opened settings dialog")
        except Exception as e:
            logger.error(f"Failed to open settings window: {e}")

    def _show_notification(self, message: str, duration: int):
        """Centralized notification gate."""
        if self.get_runtime_settings().get('notifications_enabled', True):
            self.ui.show_notification(message, duration)

    def open_custom_context_file(self):
        """Open user custom context command JSON."""
        path = Path(__file__).parent / 'custom_context_commands.json'
        if not path.exists():
            path.write_text('{\n    "rules": []\n}\n', encoding='utf-8')
        try:
            subprocess.Popen(['notepad.exe', str(path)])
        except Exception as e:
            logger.error(f"Failed to open custom context file: {e}")

    def open_custom_plugin_folder(self):
        """Open/create custom plugin folder for user-developed extensions."""
        folder = Path(__file__).parent / 'custom_plugins'
        folder.mkdir(parents=True, exist_ok=True)
        readme = folder / 'README.md'
        if not readme.exists():
            readme.write_text(
                "# Custom Plugins\n\n"
                "Drop Python modules here.\n\n"
                "Optional exports:\n"
                "- `get_commands()` -> list of {'name','description','callback'}\n"
                "- `get_mode_handlers(state_machine)` -> dict[MenuMode, handler]\n",
                encoding='utf-8'
            )
        try:
            os.startfile(str(folder))
        except Exception as e:
            logger.error(f"Failed to open custom plugin folder: {e}")

    def get_macro_config_path(self) -> str:
        return str(self.macro_manager.get_config_path())

    def open_macro_editor(self) -> bool:
        """Open Macro Studio dialog."""
        logger.info("open_macro_editor invoked")
        try:
            logger.info("open_macro_editor: deactivating macro manager")
            self.macro_manager.deactivate()
            if hasattr(self.ui, "hide_menu"):
                logger.info("open_macro_editor: hiding wheel UI")
                self.ui.hide_menu()
            if hasattr(self.ui, "ensure_cursor_visible"):
                self.ui.ensure_cursor_visible()
            logger.info("open_macro_editor: checking dialog instance")
            needs_create = self.macro_editor_dialog is None
            if not needs_create:
                try:
                    _ = self.macro_editor_dialog.isVisible()
                except RuntimeError:
                    # Wrapped Qt object was deleted; recreate safely.
                    needs_create = True
                    self.macro_editor_dialog = None

            if needs_create:
                # Keep Macro Studio as a top-level window so it can open independently
                # of the Settings dialog visibility/focus state.
                logger.info("open_macro_editor: creating MacroEditorDialog")
                self.macro_editor_dialog = MacroEditorDialog(
                    config_path=self.macro_manager.get_config_path(),
                    on_saved=self.reload_macro_config,
                    parent=None,
                )
                self.macro_editor_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
                self.macro_editor_dialog.destroyed.connect(lambda *_: setattr(self, "macro_editor_dialog", None))
            logger.info("Opening Macro Studio dialog")
            screen = QGuiApplication.primaryScreen()
            if screen:
                available = screen.availableGeometry()
                frame = self.macro_editor_dialog.frameGeometry()
                frame.moveCenter(available.center())
                self.macro_editor_dialog.move(frame.topLeft())
            self.macro_editor_dialog.show()
            self.macro_editor_dialog.showNormal()
            self.macro_editor_dialog.raise_()
            self.macro_editor_dialog.activateWindow()
            logger.info("open_macro_editor: show/raise complete")
            return True
        except Exception as e:
            logger.exception(f"Failed to open macro editor: {e}")
            self._show_notification("Failed to open Macro Studio", 1800)
            return False

    def reload_macro_config(self):
        try:
            self.macro_manager.reload()
            self._show_notification("Macro config reloaded", 1000)
        except Exception as e:
            logger.error(f"Failed to reload macro config: {e}")

    def get_available_themes(self) -> List[str]:
        """Return theme names from themes.json if available."""
        themes_path = Path(__file__).parent / 'themes.json'
        if themes_path.exists():
            try:
                with open(themes_path, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and data:
                        return list(data.keys())
            except Exception:
                pass
        return ['DARK', 'LIGHT', 'CYBER']

    def set_theme(self, theme_name: str):
        """Persist and apply theme."""
        if not theme_name:
            return
        self.config['ui_theme'] = theme_name
        if QThread.currentThread() == self.app.thread():
            self.ui.set_theme(theme_name)
        self._save_config()

    def setup(self) -> bool:
        """Initialize all components"""
        logger.info("Initializing KnobDeck (Qt)...")

        # Check API status
        status = self.api.get_status()
        for name, available in status.items():
            level = logging.INFO if available else logging.WARNING
            logger.log(level, f"API {name}: {'Available' if available else 'Unavailable'}")

        if not self.api.is_available():
            logger.error("No Windows APIs available! Install requirements.")
            return False

        # Try to connect to Voicemeeter if enabled
        logger.info("Configuring Voicemeeter integration...")
        self._reconfigure_voicemeeter_runtime()
        if self._is_voicemeeter_enabled() and self.vm.is_available() and self.get_runtime_settings().get('restore_voicemeeter_on_start', False):
            saved_vm_state = self.config.get('voicemeeter_state')
            if isinstance(saved_vm_state, dict):
                try:
                    self.vm.apply_state(saved_vm_state)
                    logger.info("Restored saved Voicemeeter state from config")
                except Exception as e:
                    logger.warning(f"Failed to restore Voicemeeter state: {e}")

        self._rebuild_runtime_bindings()

        # Link state machine to components
        self.state_machine.api = self.api
        self.state_machine.vm = self.vm
        self.state_machine.signalrgb = self.signalrgb
        self.state_machine.set_ui_callback(self._ui_callback)
        self.state_machine.set_ui_hide_callback(self.ui.hide_menu)
        self.state_machine.apply_settings(self.get_runtime_settings())
        self.state_machine.set_notification_callback(self._show_notification)

        # Start UI
        logger.info("Starting UI...")
        self.ui.start()
        if hasattr(self.ui, 'set_side_label_max_chars'):
            self.ui.set_side_label_max_chars(int(self.get_runtime_settings().get('side_label_max_chars', 18)))

        # Start tray icon
        self.tray_icon.start()

        # Connect to HID device (heartbeat-only)
        result = self._connect_hid()

        # Register global hotkeys for encoder events (F13-F18)
        self._setup_hotkeys()

        # Start timeout timer (1Hz)
        self.timeout_timer = QTimer(self)
        self.timeout_timer.timeout.connect(self._check_timeout)
        self.timeout_timer.start(1000)

        self.click_confirm_timer = QTimer(self)
        self.click_confirm_timer.setSingleShot(True)
        self.click_confirm_timer.timeout.connect(self._execute_pending_release)

        self.hidden_tap_timer = QTimer(self)
        self.hidden_tap_timer.setSingleShot(True)
        self.hidden_tap_timer.timeout.connect(self._finalize_hidden_taps)

        self.macro_toggle_timer = QTimer(self)
        self.macro_toggle_timer.setSingleShot(True)
        self.macro_toggle_timer.timeout.connect(self._execute_pending_macro_toggle)

        self.profile_timer = QTimer(self)
        self.profile_timer.timeout.connect(self._check_profile_switch)
        self.profile_timer.start(750)

        self.plugin_watch_timer = QTimer(self)
        self.plugin_watch_timer.timeout.connect(self._check_plugin_hot_reload)
        self.plugin_watch_timer.start(1200)

        self._update_status_indicator()
        if self.get_runtime_settings().get("show_onboarding_on_start", True) and not self.get_runtime_settings().get("onboarding_completed", False):
            QTimer.singleShot(900, self.open_onboarding_tutorial)
        
        return result

    def _check_profile_switch(self):
        """Auto-switch profile based on active app context rules."""
        if not self.get_runtime_settings().get('auto_profile_switch_enabled', True):
            return
        try:
            ctx = context_manager.detector.get_current_context()
            profile = self._resolve_profile_for_context(ctx)
            self._apply_profile(profile)
        except Exception as e:
            logger.debug(f"Profile switch check failed: {e}")

    def _check_timeout(self):
        """Check for menu timeout"""
        if self.is_pressed:
            return
        if self.state_machine.check_menu_timeout():
            if self.state_machine.state.menu_mode == MenuMode.NORMAL:
                # Clear timer and hide menu
                self.state_machine.state.menu_timer = None
                self.ui.hide_menu()
            else:
                self.state_machine.exit_menu_mode()

    def _connect_hid(self) -> bool:
        """Set up the event signal carrier.

        The firmware now delivers encoder events as F13-F18 keyboard
        shortcuts, so we do NOT open the HID device here.  Opening it would
        compete with VIA (Chrome WebHID) for exclusive access and cause the
        'Receiving incorrect response' errors.  The HIDReaderThread object is
        created only to provide the event_received signal that _setup_hotkeys
        will emit into.
        """
        config = self.config
        self.hid_reader = HIDReaderThread(
            vendor_id=config['hid']['vendor_id'],
            product_id=config['hid']['product_id'],
            usage_page=config['hid']['usage_page'],
            usage=config['hid']['usage']
        )

        # Wire up the signal — hotkeys will emit it; the thread is never started
        self.hid_reader.event_received.connect(self._on_hid_event)

        logger.info("Event signal carrier ready (no HID connection — VIA has exclusive access)")
        return True

    def _setup_hotkeys(self):
        """Register F13-F18 global hotkeys for encoder events.

        Firmware sends these shortcuts instead of raw HID packets so VIA can
        use the HID endpoint uncontested.

        Shortcut → event mapping (mirrors firmware EVT_ENCODER_* constants):
          F13 = CW rotation   F14 = CCW rotation
          F15 = Press         F16 = Release
          F17 = Long press    F18 = Double tap
        """
        try:
            import keyboard as kb_lib
        except ImportError:
            logger.error("'keyboard' package not found — install it: pip install keyboard")
            return

        # Aliases so lambdas capture constants, not the HIDReaderThread names
        EV_CW     = HIDReaderThread.EVENT_CW           # 0x01
        EV_CCW    = HIDReaderThread.EVENT_CCW          # 0x02
        EV_PRESS  = HIDReaderThread.EVENT_PRESS        # 0x03
        EV_REL    = HIDReaderThread.EVENT_RELEASE      # 0x04
        EV_LONG   = HIDReaderThread.EVENT_LONG_PRESS   # 0x05
        EV_DBL    = HIDReaderThread.EVENT_DOUBLE_CLICK # 0x06

        sig = self.hid_reader.event_received  # pyqtSignal — safe to emit from threads

        kb_lib.add_hotkey('f13', lambda: sig.emit(EV_CW,    0, 1), suppress=True)
        kb_lib.add_hotkey('f14', lambda: sig.emit(EV_CCW,   0, 1), suppress=True)
        kb_lib.add_hotkey('f15', lambda: sig.emit(EV_PRESS, 0, 0), suppress=True)
        kb_lib.add_hotkey('f16', lambda: sig.emit(EV_REL,   0, 0), suppress=True)
        kb_lib.add_hotkey('f17', lambda: sig.emit(EV_LONG,  0, 0), suppress=True)
        kb_lib.add_hotkey('f18', lambda: sig.emit(EV_DBL,   0, 0), suppress=True)

        self._hotkeys_registered = True
        logger.info("Global hotkeys registered: F13-F18")

    @pyqtSlot(int, int, int)
    def _on_hid_event(self, event_type: int, encoder_id: int, value: int):
        """Handle HID event (called on main thread via signal)"""
        if event_type == HIDReaderThread.EVENT_CW:
            self._handle_rotation(True, value)
        elif event_type == HIDReaderThread.EVENT_CCW:
            self._handle_rotation(False, value)
        elif event_type == HIDReaderThread.EVENT_PRESS:
            if not self.is_pressed:
                self._handle_press()
            else:
                logger.debug("Ignoring duplicate encoder press event")
        elif event_type == HIDReaderThread.EVENT_RELEASE:
            if self.is_pressed:
                self._handle_release()
            else:
                logger.debug("Ignoring duplicate encoder release event")
        elif event_type == HIDReaderThread.EVENT_LONG_PRESS:
            self._handle_long_press()
        elif event_type == HIDReaderThread.EVENT_DOUBLE_CLICK:
            self._handle_double_tap()

    @pyqtSlot()
    def _on_hid_connected(self):
        """HID device connected"""
        logger.info("HID device connected")
        self._show_notification("Keyboard Connected", 1500)

    @pyqtSlot()
    def _on_hid_disconnected(self):
        """HID device disconnected"""
        logger.warning("HID device disconnected - attempting reconnect")
        self._show_notification("Keyboard Disconnected", 2000)

    def _handle_rotation(self, clockwise: bool, steps: int = 1):
        """Handle encoder rotation"""
        import time
        current_time = time.time()
        steps = max(1, steps)

        if self.hidden_tap_timer and self.hidden_tap_timer.isActive():
            self.hidden_tap_timer.stop()
            self.hidden_tap_count = 0

        # If user starts rotating, any pending single-click action is stale.
        if self.click_confirm_timer and self.click_confirm_timer.isActive():
            self.click_confirm_timer.stop()
            self.pending_press_mode = None
            self.pending_macro_execute = False

        # Safety: If we think we are pressed but haven't seen activity in 1.5s, we missed a release
        if self.is_pressed and (current_time - self.last_activity_time) > 1.5:
            logger.warning("Detected stuck press state - forcing release")
            self.is_pressed = False
            self.was_rotated_while_pressed = False
            self._hide_volume_wheel()

        self.last_activity_time = current_time

        # Check if button is held for quick volume change
        if self.is_pressed and self.long_press_active:
            if self.macro_manager.active:
                # In macro mode, hold+rotate switches macro layer.
                self.was_rotated_while_pressed = True
                delta = max(1, int(steps))
                for _ in range(delta):
                    self.macro_manager.cycle_layer(1 if clockwise else -1)
                return

            logger.debug("Quick volume: rotation while pressed")
            self.was_rotated_while_pressed = True

            # Direct volume adjustment when button is held
            step = max(1, int(self.get_runtime_settings().get('volume_step', 2)))
            delta = (step * steps) if clockwise else (-step * steps)
            self.api.volume.adjust_volume(delta)
            vol = self.api.volume.get_volume()

            # Show volume wheel with progress
            display = {
                'left': '−',
                'center': f'{vol}%',
                'right': '+',
                'title': '🔊 System Volume',
                'subtitle': 'Hold & Turn',
                'active_index': 1
            }
            progress = vol / 100.0
            icons = {'left': '−', 'center': '🔊', 'right': '+'}

            display['left'] = '-'
            display['title'] = 'System Volume'
            icons['left'] = '-'
            icons['center'] = 'VOL'

            # Reset timer to prevent old menu from showing
            self.state_machine.state.menu_timer = None

            self.ui.show_menu(display, progress=progress, icons=icons)

            # Set auto-hide timer (hide after 800ms of no activity)
            if self.volume_hide_timer:
                self.volume_hide_timer.stop()
            self.volume_hide_timer = QTimer(self)
            self.volume_hide_timer.setSingleShot(True)
            self.volume_hide_timer.timeout.connect(self._hide_volume_wheel)
            self.volume_hide_timer.start(self.quick_volume_hide_ms)

            return  # Early return - don't cycle commands

        if self.is_pressed:
            logger.debug("Ignoring rotation while pressed before long-press threshold")
            return

        if self.macro_manager.active:
            self.macro_manager.rotate_selection(clockwise, steps)
            return

        if self.state_machine.state.menu_mode != MenuMode.NORMAL:
            self.state_machine.handle_rotation_direction(clockwise)
            return

        # Calculate new simulated index
        # We need to simulate an absolute 0-3 rotation for the state machine
        # which expects absolute values to detect direction or set command
        count = self.state_machine.commands.count()
        if count == 0: count = 4

        # Clockwise: left→center, Counter-clockwise: right→center
        direction = -1 if clockwise else 1
        new_index = self.last_command_index
        for _ in range(steps):
            new_index = (new_index + direction) % count
            self.state_machine.handle_rotation(new_index)

        # Update our local tracking
        self.last_command_index = new_index

    def _handle_press(self):
        """Handle encoder press"""
        import time
        logger.info("Press detected")
        if self.click_confirm_timer and self.click_confirm_timer.isActive():
            self.click_confirm_timer.stop()
            self.pending_press_mode = None
        self.is_pressed = True
        self.long_press_active = False
        self.was_rotated_while_pressed = False
        self.last_activity_time = time.time()

    def _hide_volume_wheel(self):
        """Hide the volume wheel (called by timer or release)"""
        logger.debug(f"_hide_volume_wheel called: mode={self.state_machine.state.menu_mode}, is_pressed={self.is_pressed}")
        if self.state_machine.state.menu_mode == MenuMode.NORMAL:
            # If timer fired during quick volume, firmware didn't send release - force it
            if self.is_pressed and self.was_rotated_while_pressed:
                logger.info("Quick volume finished - forcing release state")
                self.is_pressed = False
                self.was_rotated_while_pressed = False

            logger.info("Hiding volume wheel now")
            self.ui.hide_menu()
            self.state_machine.state.menu_timer = None
            if self.volume_hide_timer:
                self.volume_hide_timer.stop()
                self.volume_hide_timer = None

    def _handle_release(self):
        """Handle encoder release"""
        import time
        logger.info(f"Release detected: was_rotated={self.was_rotated_while_pressed}, mode={self.state_machine.state.menu_mode}")
        self.last_activity_time = time.time()

        if self.ignore_next_release:
            self.ignore_next_release = False
            self.is_pressed = False
            self.long_press_active = False
            self.was_rotated_while_pressed = False
            return

        if self.long_press_active and not self.was_rotated_while_pressed:
            self.api.volume.toggle_mute()
            muted = self.api.volume.get_mute()
            self._show_notification("Muted" if muted else "Unmuted", 1200)
        elif not self.was_rotated_while_pressed:
            if self.macro_manager.active:
                # Delay macro execution so a double-click can cancel it to close Macro Mode.
                if self.click_confirm_timer:
                    delay_ms = int(self.get_runtime_settings().get('double_click_ms', 300))
                    self.pending_macro_execute = True
                    self.click_confirm_timer.start(delay_ms)
                self.is_pressed = False
                self.long_press_active = False
                self.was_rotated_while_pressed = False
                return

            is_idle_normal = (
                self.state_machine.state.menu_mode == MenuMode.NORMAL
                and self.state_machine.state.menu_timer is None
            )
            if is_idle_normal and self.get_runtime_settings().get('triple_click_settings_enabled', True):
                self._register_hidden_taps(1)
            else:
            # Delay single-click action until the firmware double-tap window passes.
            # This prevents "double-click to go back" from also toggling submenu actions.
                if self.click_confirm_timer:
                    delay_ms = int(self.get_runtime_settings().get('double_click_ms', 300))
                    self.pending_press_mode = self.state_machine.state.menu_mode
                    self.click_confirm_timer.start(delay_ms)
        else:
            # We rotated while pressed - this was quick volume
            if self.state_machine.state.menu_mode == MenuMode.NORMAL:
                # Quick volume mode - trigger immediate hide (timer will also fire as backup)
                logger.debug("Hiding volume wheel after quick volume")
                self._hide_volume_wheel()
            else:
                # In menu mode, refresh display
                self.state_machine.reset_menu_timer()
                self.state_machine.update_display()

        self.is_pressed = False
        self.long_press_active = False
        self.was_rotated_while_pressed = False

    def _handle_double_tap(self):
        """Handle encoder double-tap"""
        if self.click_confirm_timer and self.click_confirm_timer.isActive():
            self.click_confirm_timer.stop()
            self.pending_press_mode = None
        self.pending_macro_execute = False

        # Double-click while Macro Mode is active closes it without executing.
        if self.macro_manager.active:
            self.macro_manager.deactivate()
            self.ignore_next_release = True
            return

        is_idle_normal = (
            self.state_machine.state.menu_mode == MenuMode.NORMAL
            and self.state_machine.state.menu_timer is None
        )
        if is_idle_normal and self.get_runtime_settings().get('macro_mode_enabled', True):
            # If triple-click is enabled, defer macro toggle until the triple-click
            # window passes so a 3rd click can open Settings instead.
            if self.get_runtime_settings().get('triple_click_settings_enabled', True):
                self.pending_macro_toggle = True
                if self.macro_toggle_timer:
                    window_ms = int(self.get_runtime_settings().get('triple_click_window_ms', 700))
                    self.macro_toggle_timer.start(window_ms)
                return

            self.macro_manager.toggle()
            self.ignore_next_release = True
            return

        if is_idle_normal and self.get_runtime_settings().get('triple_click_settings_enabled', True):
            # In idle mode without macro-mode toggle, triple-click is counted from releases.
            return

        self.ignore_next_release = True
        self.state_machine.handle_double_tap()

    def _handle_long_press(self):
        """Arm long-press behavior for mute or held volume control."""
        import time
        if not self.is_pressed:
            return
        logger.info("Long press detected")
        self.long_press_active = True
        self.last_activity_time = time.time()

    def _execute_pending_release(self):
        """Execute the press action after the double-tap window expires."""
        if not self.is_pressed:
            if self.pending_macro_execute:
                self.pending_macro_execute = False
                if self.macro_manager.active:
                    self.macro_manager.execute_selected()
                return
            # Only execute if we are still in the same mode where click was queued.
            if self.pending_press_mode is not None and self.pending_press_mode != self.state_machine.state.menu_mode:
                self.pending_press_mode = None
                return
            self.state_machine.handle_press()
        self.pending_press_mode = None

    def _execute_pending_macro_toggle(self):
        """Toggle Macro Mode after triple-click window if not superseded by Settings action."""
        if not self.pending_macro_toggle:
            return
        self.pending_macro_toggle = False
        if self.state_machine.state.menu_mode == MenuMode.NORMAL and self.state_machine.state.menu_timer is None:
            self.macro_manager.toggle()

    def _register_hidden_taps(self, increment: int):
        """Register idle taps for special actions (e.g. triple-click open settings)."""
        import time

        window_ms = int(self.get_runtime_settings().get('triple_click_window_ms', 700))
        now_ms = int(time.time() * 1000)
        if (now_ms - self.last_hidden_tap_ms) > window_ms:
            self.hidden_tap_count = 0
        self.last_hidden_tap_ms = now_ms
        self.hidden_tap_count += max(1, int(increment))
        logger.info(f"Hidden tap count: {self.hidden_tap_count}")

        if self.hidden_tap_count >= 3:
            if self.hidden_tap_timer and self.hidden_tap_timer.isActive():
                self.hidden_tap_timer.stop()
            if self.macro_toggle_timer and self.macro_toggle_timer.isActive():
                self.macro_toggle_timer.stop()
            self.pending_macro_toggle = False
            self.hidden_tap_count = 0
            self.open_settings_window()
            return

        if self.hidden_tap_timer:
            self.hidden_tap_timer.start(window_ms)

    def _finalize_hidden_taps(self):
        """Finalize idle tap sequence when triple-click window expires."""
        taps = self.hidden_tap_count
        self.hidden_tap_count = 0

        # Single click from idle retains normal behavior (show main menu).
        if taps == 1:
            self.state_machine.handle_press()

    def _register_commands(self):
        """Register main commands"""
        from functools import partial

        def _tracked(name: str, callback):
            def _wrapped():
                self._record_recent_action(name, callback)
                callback()
            return _wrapped

        commands = [
            ("Media Controls", "Play/Pause, Next/Prev", _tracked("Media Controls", partial(self.state_machine.enter_mode, MenuMode.MEDIA))),
            ("Volume", "System volume control", _tracked("Volume", partial(self.state_machine.enter_mode, MenuMode.VOLUME))),
            ("Volume Mixer", "Per-app audio sessions", _tracked("Volume Mixer", partial(self.state_machine.enter_mode, MenuMode.VOLUME_MIXER))),
            ("Recent Actions", "Re-run last actions", _tracked("Recent Actions", partial(self.state_machine.enter_mode, MenuMode.RECENT_ACTIONS))),
            ("Window Management", "Cycle, Snap, Desktop", _tracked("Window Management", partial(self.state_machine.enter_mode, MenuMode.WINDOW_MENU))),
            ("Lighting", "SignalRGB lighting controls", _tracked("Lighting", partial(self.state_machine.enter_mode, MenuMode.LIGHTING_MENU))),
            ("Theme Settings", "UI customization", _tracked("Theme Settings", partial(self.state_machine.enter_mode, MenuMode.THEME_MENU))),
        ]

        # Add Voicemeeter if enabled and available
        if self._is_voicemeeter_enabled() and self.vm.is_available():
            commands.append(("Voicemeeter", "Audio routing", _tracked("Voicemeeter", partial(self.state_machine.enter_mode, MenuMode.VOICEMEETER_MENU))))

        for name, desc, callback in commands:
            self.state_machine.commands.register(name, desc, callback)

        logger.info(f"Registered {len(commands)} main commands")

    def _reload_builtin_handlers(self):
        """Rebuild built-in handlers (used after profile changes)."""
        vm_controller = self.vm if (self._is_voicemeeter_enabled() and self.vm.is_available()) else None
        handlers = create_handlers(
            self.api,
            self.state_machine,
            vm_controller,
            self.signalrgb,
            recent_provider=self.get_recent_actions,
        )
        for mode, handler in handlers.items():
            self.state_machine.register_mode_handler(mode, handler)

    def _reconfigure_voicemeeter_runtime(self):
        """Connect/disconnect Voicemeeter integration based on settings."""
        if self._is_voicemeeter_enabled():
            if not self.vm.is_available():
                if self.vm.connect():
                    logger.info("Voicemeeter connected (enabled in settings)")
                    self.vm.set_state_change_callback(self._persist_voicemeeter_state)
                    vm_profile = self.app_settings.get('voicemeeter_profile')
                    if isinstance(vm_profile, dict) and vm_profile:
                        self.vm.apply_profile(vm_profile)
                else:
                    logger.warning("Voicemeeter enabled but unavailable")
        else:
            if self.vm.is_available():
                self.vm.disconnect()
                logger.info("Voicemeeter integration disabled by settings")

    def _rebuild_runtime_bindings(self):
        """Rebuild commands, handlers, and plugin integrations."""
        self.state_machine.commands.commands = []
        self.state_machine.mode_handlers = {}
        self.plugin_manager = PluginManager()

        self._register_commands()

        context_manager.enabled = self._is_context_enabled()

        if self._is_plugins_enabled():
            plugin_dirs = self.get_runtime_settings().get('plugin_dirs', ['custom_plugins'])
            if not isinstance(plugin_dirs, list):
                plugin_dirs = ['custom_plugins']
            disabled_plugins = set()
            auto_disabled = self.get_runtime_settings().get('disabled_plugins_auto', [])
            if isinstance(auto_disabled, list):
                disabled_plugins.update({str(x) for x in auto_disabled})
            if not self._is_context_enabled():
                disabled_plugins.add('context_commands')
            plugin_settings = self.get_runtime_settings().get('plugin_settings', {})
            if not isinstance(plugin_settings, dict):
                plugin_settings = {}
            self.plugin_manager.load_plugins(
                self.state_machine,
                plugin_dirs=plugin_dirs,
                disabled_plugin_names=disabled_plugins,
                plugin_settings=plugin_settings,
            )
            if self.plugin_manager.failed_plugins:
                auto_set = set(auto_disabled if isinstance(auto_disabled, list) else [])
                auto_set.update(self.plugin_manager.failed_plugins.keys())
                self.app_settings['disabled_plugins_auto'] = sorted(auto_set)
                self._save_config()
                logger.warning(f"Auto-disabled plugins after load failures: {sorted(self.plugin_manager.failed_plugins.keys())}")
        else:
            logger.info("Plugin integrations disabled by settings")

        self._all_commands = {cmd.name: cmd for cmd in self.state_machine.commands.commands}
        self._apply_command_layout(persist=False)
        self._reload_builtin_handlers()

        for mode, handler in self.plugin_manager.plugin_handlers.items():
            self.state_machine.register_mode_handler(mode, handler)

        if self.state_machine.state.current_command >= self.state_machine.commands.count():
            self.state_machine.state.current_command = 0
            self.last_command_index = 0

    def _ui_callback(self, data: dict):
        """Handle UI callback from state machine"""
        if 'set_theme' in data:
            theme_name = data['set_theme']
            self.ui.set_theme(theme_name)
            self.config['ui_theme'] = theme_name
            self._save_config()

        if 'preview_theme' in data:
            self.ui.set_theme(data['preview_theme'])

        if 'set_theme_color' in data:
            self.ui.update_theme_color(data['set_theme_color'])

        if 'save_theme' in data:
            self.ui.save_theme(data['save_theme'])

        # Standard menu display update should still happen even when side-effect keys exist.
        display = dict(data)
        for key in ('set_theme', 'preview_theme', 'set_theme_color', 'save_theme'):
            display.pop(key, None)
        if any(k in display for k in ('left', 'center', 'right', 'title', 'subtitle', 'active_index', 'pulsing', 'progress', 'icons')):
            display['subtitle'] = self._build_breadcrumb(display)
            progress = display.get('progress')
            icons = display.get('icons')
            theme_override = display.get('theme_override')
            if not isinstance(theme_override, dict):
                theme_override = self._mode_accent_override(self.state_machine.state.menu_mode)
            self.ui.show_menu(display, progress=progress, icons=icons, theme_override=theme_override)
            self._update_status_indicator()

    def _save_config(self):
        """Save configuration to file"""
        config_file = Path(__file__).parent / 'config.json'
        try:
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def _persist_voicemeeter_state(self):
        """Persist current Voicemeeter state to config.json."""
        if not self.vm or not self.vm.is_available():
            return
        try:
            self.config['voicemeeter_state'] = self.vm.get_state()
            self._save_config()
        except Exception as e:
            logger.warning(f"Failed to persist Voicemeeter state: {e}")

    def quit(self):
        """Cleanup and exit"""
        logger.info("Shutting down...")

        if self._hotkeys_registered:
            try:
                import keyboard as kb_lib
                kb_lib.unhook_all()
            except Exception:
                pass

        try:
            self.macro_manager.deactivate()
        except Exception:
            pass

        if self.plugin_watch_timer:
            self.plugin_watch_timer.stop()
            self.plugin_watch_timer = None
        if self.profile_timer:
            self.profile_timer.stop()
            self.profile_timer = None
        if self.timeout_timer:
            self.timeout_timer.stop()
            self.timeout_timer = None

        # HID thread is never started (keyboard-shortcut architecture), nothing to stop

        if self.vm:
            self.vm.disconnect()

        self.ui.quit()
        self.app.quit()


class KnobDeckApp(KeychronApp):
    """Neutral alias for the main application class."""
    pass


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def load_config():
    """Load configuration from config.json"""
    config_file = Path(__file__).parent / 'config.json'

    default_config = {
        'keyboard_profile_id': 'default_qmk_knob',
        'hid': {
            'vendor_id': 0x3434,
            'product_id': 0x0311,
            'usage_page': 0xFF60,
            'usage': 0x61
        },
        'ui_theme': 'DARK',
        'use_enhanced_ui': True,
        'led_feedback': False,
        'voicemeeter_state': {},
        'app_settings': {
            'menu_timeout_ms': 3000,
            'double_click_ms': 300,
            'volume_step': 2,
            'quick_volume_hide_ms': 800,
            'triple_click_settings_enabled': True,
            'triple_click_window_ms': 700,
            'side_label_max_chars': 18,
            'lighting_backend': 'signalrgb',
            'macro_mode_enabled': True,
            'enable_voicemeeter_integration': True,
            'enable_plugin_integrations': True,
            'enable_context_commands': True,
            'plugin_hot_reload_enabled': True,
            'auto_profile_switch_enabled': True,
            'show_status_indicator': True,
            'show_onboarding_on_start': True,
            'onboarding_completed': False,
            'active_profile_name': 'Default',
            'profiles': [
                {
                    'name': 'Default',
                    'priority': 0,
                    'theme': '',
                    'command_order': [],
                    'command_hidden': [],
                    'macro_layer': None,
                    'auto_switch': {},
                },
                {
                    'name': 'Browser',
                    'priority': 10,
                    'theme': '',
                    'command_order': [],
                    'command_hidden': [],
                    'macro_layer': None,
                    'auto_switch': {'process_regex': r'^(chrome|msedge|firefox|brave|opera)\\.exe$'},
                },
                {
                    'name': 'Studio',
                    'priority': 20,
                    'theme': '',
                    'command_order': [],
                    'command_hidden': [],
                    'macro_layer': None,
                    'auto_switch': {'process_regex': r'^(obs64|voicemeeter\\w*)\\.exe$'},
                },
            ],
            'notifications_enabled': True,
            'submenu_timeout_enabled': True,
            'restore_voicemeeter_on_start': False,
            'voicemeeter_profile': {
                'mic_strip': 0,
                'main_strip': 5,
                'music_strip': 6,
                'comm_strip': 7,
                'variant': 'potato',
                'active_outputs': ['A1', 'A2', 'A3', 'A4', 'A5', 'B1', 'B2', 'B3'],
                'output_names': {
                    'A1': 'Speakers',
                    'A2': 'Wired',
                    'A3': 'Wireless',
                    'A4': 'Alt 1',
                    'A5': 'Alt 2',
                    'B1': 'Virtual Out 1',
                    'B2': 'Virtual Out 2',
                    'B3': 'Virtual Out 3',
                },
                'output_icons': {
                    'A1': 'SPK',
                    'A2': 'WIR',
                    'A3': 'WLS',
                    'A4': 'A4',
                    'A5': 'A5',
                    'B1': 'B1',
                    'B2': 'B2',
                    'B3': 'B3',
                },
            },
            'plugin_dirs': ['custom_plugins'],
            'plugin_settings': {},
            'disabled_plugins_auto': [],
            'command_order': [],
            'command_hidden': [],
            'mode_timeout_ms': {
                'VOLUME_MIXER': 5000,
                'RECENT_ACTIONS': 5000,
                'VOICEMEETER_MENU': 5000,
                'VM_MIC': 5000,
                'VM_MAIN_ROUTING': 5000,
                'VM_MUSIC_GAIN': 5000,
                'VM_MUSIC_ROUTING': 5000,
                'VM_COMM_GAIN': 5000,
                'VM_COMM_ROUTING': 5000,
                'LIGHTING_MENU': 5000,
                'LIGHTING_EFFECTS': 8000,
            },
        },
    }

    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                # Merge with defaults
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                if not isinstance(config.get('app_settings'), dict):
                    config['app_settings'] = default_config['app_settings'].copy()
                else:
                    for key, value in default_config['app_settings'].items():
                        if key not in config['app_settings']:
                            config['app_settings'][key] = value
                return config
        except Exception as e:
            logger.error(f"Error loading config: {e}")

    return default_config


def main():
    """Main entry point"""
    import argparse

    # If launched with python.exe on Windows, relaunch detached with pythonw.exe
    # so the app survives terminal closure and does not show a console window.
    if (
        os.name == 'nt'
        and Path(sys.executable).name.lower() == 'python.exe'
        and '--no-detach' not in sys.argv[1:]
    ):
        pythonw_path = Path(sys.executable).with_name('pythonw.exe')
        if pythonw_path.exists():
            try:
                script_path = str(Path(__file__).resolve())
                relaunch_args = [str(pythonw_path), script_path]
                relaunch_args.extend(arg for arg in sys.argv[1:] if arg != '--no-detach')
                relaunch_args.append('--detached-child')

                creation_flags = 0
                creation_flags |= getattr(subprocess, 'DETACHED_PROCESS', 0)
                creation_flags |= getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
                creation_flags |= getattr(subprocess, 'CREATE_NO_WINDOW', 0)

                subprocess.Popen(
                    relaunch_args,
                    cwd=str(Path(__file__).resolve().parent),
                    close_fds=True,
                    creationflags=creation_flags
                )
                return 0
            except Exception as e:
                logger.warning(f"Failed to relaunch with pythonw.exe: {e}")

    # Load config
    config = load_config()

    # Parse arguments
    parser = argparse.ArgumentParser(description='KnobDeck (Qt)')

    # Load available themes
    available_themes = ['DARK', 'LIGHT', 'CYBER']
    themes_path = Path(__file__).parent / 'themes.json'
    if themes_path.exists():
        try:
            with open(themes_path, 'r') as f:
                available_themes = list(json.load(f).keys())
        except:
            pass

    parser.add_argument('--theme', choices=available_themes, default=None,
                       help=f'UI theme. Available: {", ".join(available_themes)}')
    parser.add_argument('--no-detach', action='store_true',
                       help='Do not auto-relaunch with pythonw.exe')
    parser.add_argument('--detached-child', action='store_true',
                       help=argparse.SUPPRESS)

    args = parser.parse_args()

    # Single-instance guard (Windows): avoid duplicate app processes competing
    # for hooks/hotkeys and creating inconsistent UI behavior.
    global _instance_lock_file
    global _instance_mutex_handle
    if os.name == 'nt':
        try:
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            mutex_name = "Local\\KnobDeckQtSingleton"
            kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
            kernel32.CreateMutexW.restype = ctypes.c_void_p
            ctypes.set_last_error(0)
            _instance_mutex_handle = kernel32.CreateMutexW(None, False, mutex_name)
            if _instance_mutex_handle and ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
                logger.info("Another KnobDeck instance is already running; exiting duplicate.")
                return 0
        except Exception as e:
            logger.warning(f"Single-instance mutex unavailable: {e}")
            try:
                import msvcrt
                lock_path = Path(tempfile.gettempdir()) / 'knobdeck_qt.lock'
                _instance_lock_file = open(lock_path, 'a+', encoding='utf-8')
                _instance_lock_file.seek(0)
                try:
                    msvcrt.locking(_instance_lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    logger.info("Another KnobDeck instance is already running; exiting duplicate.")
                    return 0
                _instance_lock_file.truncate(0)
                _instance_lock_file.write(str(os.getpid()))
                _instance_lock_file.flush()
            except Exception as inner:
                logger.warning(f"Single-instance lock fallback unavailable: {inner}")

    # Override config with args
    if args.theme is not None:
        config['ui_theme'] = args.theme
    if config.get('ui_theme') not in available_themes:
        config['ui_theme'] = 'DARK'

    # Create Qt application (MUST be on main thread)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running with tray icon
    app_icon = Path(__file__).parent / "assets" / "knobdeck_logo.png"
    if app_icon.exists():
        app.setWindowIcon(QIcon(str(app_icon)))

    # Create and setup our app
    knobdeck_app = KnobDeckApp(config, app)

    if not knobdeck_app.setup():
        logger.error("Failed to initialize application")
        return 1

    logger.info("Application started. Running Qt event loop...")

    # Run Qt event loop (blocking)
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
