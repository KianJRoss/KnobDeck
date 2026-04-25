"""
Context-Aware Commands System
Detects active application and provides relevant commands
"""

import logging
import json
import os
import subprocess
import webbrowser
import win32gui
import win32process
import psutil
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass

logger = logging.getLogger("KeychronApp.ContextAware")


@dataclass
class ContextCommand:
    """A context-specific command"""
    name: str
    description: str
    callback: Callable
    icon: Optional[str] = None


@dataclass
class AppContext:
    """Application context information"""
    process_name: str
    window_title: str
    exe_path: str
    hwnd: int


class ContextDetector:
    """Detect current application context"""

    def __init__(self):
        self.last_context: Optional[AppContext] = None
        self.last_check_time = 0
        self.check_interval = 0.5  # Check every 500ms

    def get_current_context(self) -> Optional[AppContext]:
        """Get current active application context"""
        current_time = time.time()

        # Rate limit checks
        if current_time - self.last_check_time < self.check_interval:
            return self.last_context

        self.last_check_time = current_time

        try:
            # Get foreground window
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None

            # Get window title
            window_title = win32gui.GetWindowText(hwnd)

            # Get process info
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)

            context = AppContext(
                process_name=process.name().lower(),
                window_title=window_title,
                exe_path=process.exe(),
                hwnd=hwnd
            )

            self.last_context = context
            return context

        except Exception as e:
            logger.debug(f"Error getting context: {e}")
            return None


class ContextProvider:
    """Base class for context-specific command providers"""

    def matches(self, context: AppContext) -> bool:
        """Check if this provider matches the given context"""
        raise NotImplementedError

    def get_commands(self, context: AppContext) -> List[ContextCommand]:
        """Get commands for this context"""
        raise NotImplementedError

    def get_priority(self) -> int:
        """Get priority (higher = more important, shown first)"""
        return 0


class CustomJsonContextProvider(ContextProvider):
    """User-defined context commands loaded from custom_context_commands.json."""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self._rules: List[Dict[str, Any]] = []
        self._mtime = 0.0

    def get_priority(self) -> int:
        return 20

    def _load_rules_if_needed(self):
        try:
            mtime = os.path.getmtime(self.config_path)
        except OSError:
            self._rules = []
            self._mtime = 0.0
            return

        if mtime == self._mtime:
            return

        self._mtime = mtime
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                rules = data.get("rules", [])
            else:
                rules = data
            self._rules = rules if isinstance(rules, list) else []
            logger.info(f"Loaded {len(self._rules)} custom context rules")
        except Exception as e:
            logger.warning(f"Failed to parse custom context commands: {e}")
            self._rules = []

    def _rule_matches(self, rule: Dict[str, Any], context: AppContext) -> bool:
        processes = rule.get("processes", [])
        titles = rule.get("window_title_contains", [])
        match_any = bool(rule.get("match_any", True))

        process_hit = True
        title_hit = True

        if isinstance(processes, list) and processes:
            process_hit = context.process_name.lower() in [str(p).lower() for p in processes]

        if isinstance(titles, list) and titles:
            title_hit = any(str(t).lower() in context.window_title.lower() for t in titles)

        return (process_hit or title_hit) if match_any else (process_hit and title_hit)

    def matches(self, context: AppContext) -> bool:
        self._load_rules_if_needed()
        for rule in self._rules:
            if isinstance(rule, dict) and self._rule_matches(rule, context):
                return True
        return False

    def _build_callback(self, action: Dict[str, Any]) -> Callable:
        action_type = str(action.get("type", "shell")).lower()

        if action_type == "url":
            url = str(action.get("url", "")).strip()
            return lambda: webbrowser.open(url)

        if action_type == "shell":
            command = str(action.get("command", "")).strip()
            return lambda: subprocess.Popen(["cmd", "/c", command], shell=False)

        if action_type == "hotkey":
            hotkey = str(action.get("hotkey", "")).strip()
            sequence = action.get("sequence", [])
            interval_ms = int(action.get("interval_ms", 40))

            def send_hotkey():
                try:
                    import keyboard as kb_lib
                except Exception as e:
                    logger.warning(f"Hotkey action requires 'keyboard' package: {e}")
                    return

                if hotkey:
                    kb_lib.send(hotkey)
                    return

                if isinstance(sequence, list):
                    for stroke in sequence:
                        key = str(stroke).strip()
                        if not key:
                            continue
                        kb_lib.send(key)
                        time.sleep(max(0, interval_ms) / 1000.0)

            return send_hotkey

        # Fallback no-op callback
        return lambda: None

    def get_commands(self, context: AppContext) -> List[ContextCommand]:
        self._load_rules_if_needed()
        commands: List[ContextCommand] = []

        for rule in self._rules:
            if not isinstance(rule, dict) or not self._rule_matches(rule, context):
                continue

            for item in rule.get("commands", []):
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "Custom Command")).strip()
                desc = str(item.get("description", "")).strip()
                icon = item.get("icon")
                action = item.get("action", {})
                if not isinstance(action, dict):
                    continue
                commands.append(
                    ContextCommand(
                        name=name,
                        description=desc,
                        callback=self._build_callback(action),
                        icon=str(icon) if icon is not None else None,
                    )
                )

        return commands


# ============================================================================
# CONTEXT PROVIDERS - Browser
# ============================================================================

class BrowserContextProvider(ContextProvider):
    """Commands for web browsers"""

    BROWSER_PROCESSES = ['chrome.exe', 'firefox.exe', 'msedge.exe', 'opera.exe', 'brave.exe']

    def matches(self, context: AppContext) -> bool:
        return context.process_name in self.BROWSER_PROCESSES

    def get_commands(self, context: AppContext) -> List[ContextCommand]:
        import win32api
        import win32con

        def new_tab():
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(0x54, 0, 0, 0)  # T
            time.sleep(0.02)
            win32api.keybd_event(0x54, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

        def close_tab():
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(0x57, 0, 0, 0)  # W
            time.sleep(0.02)
            win32api.keybd_event(0x57, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

        def reopen_tab():
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
            win32api.keybd_event(0x54, 0, 0, 0)  # T
            time.sleep(0.02)
            win32api.keybd_event(0x54, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

        def next_tab():
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(win32con.VK_TAB, 0, 0, 0)
            time.sleep(0.02)
            win32api.keybd_event(win32con.VK_TAB, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

        def prev_tab():
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
            win32api.keybd_event(win32con.VK_TAB, 0, 0, 0)
            time.sleep(0.02)
            win32api.keybd_event(win32con.VK_TAB, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

        return [
            ContextCommand("🌐 New Tab", "Open new tab (Ctrl+T)", new_tab, "➕"),
            ContextCommand("🌐 Close Tab", "Close current tab (Ctrl+W)", close_tab, "✖️"),
            ContextCommand("🌐 Reopen Tab", "Reopen closed tab (Ctrl+Shift+T)", reopen_tab, "↩️"),
            ContextCommand("🌐 Next Tab", "Switch to next tab", next_tab, "→"),
            ContextCommand("🌐 Previous Tab", "Switch to previous tab", prev_tab, "←"),
        ]

    def get_priority(self) -> int:
        return 10


# ============================================================================
# CONTEXT PROVIDERS - Code Editors
# ============================================================================

class CodeEditorContextProvider(ContextProvider):
    """Commands for code editors"""

    EDITOR_PROCESSES = ['code.exe', 'cursor.exe', 'pycharm64.exe', 'idea64.exe',
                        'sublime_text.exe', 'notepad++.exe', 'devenv.exe']

    def matches(self, context: AppContext) -> bool:
        return context.process_name in self.EDITOR_PROCESSES

    def get_commands(self, context: AppContext) -> List[ContextCommand]:
        import win32api
        import win32con

        def comment_line():
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(win32con.VK_DIVIDE, 0, 0, 0)  # /
            time.sleep(0.02)
            win32api.keybd_event(win32con.VK_DIVIDE, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

        def format_document():
            win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)  # Alt
            win32api.keybd_event(0x46, 0, 0, 0)  # F
            time.sleep(0.02)
            win32api.keybd_event(0x46, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)

        def find_in_files():
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
            win32api.keybd_event(0x46, 0, 0, 0)  # F
            time.sleep(0.02)
            win32api.keybd_event(0x46, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

        def run_debug():
            win32api.keybd_event(win32con.VK_F5, 0, 0, 0)
            time.sleep(0.02)
            win32api.keybd_event(win32con.VK_F5, 0, win32con.KEYEVENTF_KEYUP, 0)

        return [
            ContextCommand("💻 Toggle Comment", "Comment/uncomment line", comment_line, "💬"),
            ContextCommand("💻 Format Code", "Format document", format_document, "📝"),
            ContextCommand("💻 Find in Files", "Search across files", find_in_files, "🔍"),
            ContextCommand("💻 Run/Debug", "Start debugging (F5)", run_debug, "▶️"),
        ]

    def get_priority(self) -> int:
        return 10


# ============================================================================
# CONTEXT PROVIDERS - Discord
# ============================================================================

class DiscordContextProvider(ContextProvider):
    """Commands for Discord"""

    def matches(self, context: AppContext) -> bool:
        return context.process_name == 'discord.exe'

    def get_commands(self, context: AppContext) -> List[ContextCommand]:
        import win32api
        import win32con

        def toggle_mute():
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
            win32api.keybd_event(0x4D, 0, 0, 0)  # M
            time.sleep(0.02)
            win32api.keybd_event(0x4D, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

        def toggle_deafen():
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
            win32api.keybd_event(0x44, 0, 0, 0)  # D
            time.sleep(0.02)
            win32api.keybd_event(0x44, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

        return [
            ContextCommand("🎮 Toggle Mute", "Mute/unmute microphone", toggle_mute, "🎤"),
            ContextCommand("🎮 Toggle Deafen", "Deafen/undeafen audio", toggle_deafen, "🔇"),
        ]

    def get_priority(self) -> int:
        return 10


# ============================================================================
# CONTEXT MANAGER
# ============================================================================

class ContextAwareManager:
    """Manages context-aware commands"""

    def __init__(self):
        self.detector = ContextDetector()
        self.providers: List[ContextProvider] = []
        self.enabled = True
        self._register_default_providers()

    def _register_default_providers(self):
        """Register built-in context providers"""
        custom_path = os.path.join(os.path.dirname(__file__), "custom_context_commands.json")
        self.register_provider(CustomJsonContextProvider(custom_path))
        self.register_provider(BrowserContextProvider())
        self.register_provider(CodeEditorContextProvider())
        self.register_provider(DiscordContextProvider())

    def register_provider(self, provider: ContextProvider):
        """Register a new context provider"""
        self.providers.append(provider)
        # Sort by priority
        self.providers.sort(key=lambda p: p.get_priority(), reverse=True)

    def get_contextual_commands(self) -> List[ContextCommand]:
        """Get commands for current context"""
        if not self.enabled:
            return []

        context = self.detector.get_current_context()
        if not context:
            return []

        commands = []
        for provider in self.providers:
            if provider.matches(context):
                provider_commands = provider.get_commands(context)
                commands.extend(provider_commands)
                logger.debug(f"Added {len(provider_commands)} commands from {provider.__class__.__name__}")

        return commands

    def get_current_app_name(self) -> Optional[str]:
        """Get current application name"""
        context = self.detector.get_current_context()
        if context:
            return context.process_name.replace('.exe', '').title()
        return None


# Global instance
context_manager = ContextAwareManager()


# ============================================================================
# INTEGRATION HELPER
# ============================================================================

def inject_contextual_commands(command_registry, state_machine):
    """Inject contextual commands into the command registry

    This should be called periodically or on command rotation to update
    the available commands based on the active application.
    """
    # Get contextual commands
    contextual = context_manager.get_contextual_commands()

    if not contextual:
        return  # No contextual commands

    # Get app name for grouping
    app_name = context_manager.get_current_app_name()

    # Add a special command that opens a context menu
    def show_context_menu():
        # Create a custom mode to show contextual commands
        state_machine.enter_mode(MenuMode.CONTEXT_MENU)

    # Register the context menu command
    # Note: This is a simplified approach. A better implementation would
    # dynamically update the command list or show a separate menu
    logger.info(f"Found {len(contextual)} contextual commands for {app_name}")


# Export
__all__ = ['ContextAwareManager', 'ContextProvider', 'ContextCommand',
           'context_manager', 'inject_contextual_commands']
