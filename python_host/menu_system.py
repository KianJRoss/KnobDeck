"""
Keychron V1 Menu System - State Machine
Based on keychron_commands.ahk AutoHotkey v2 implementation

Architecture:
    - State machine tracks current mode (normal, menu modes)
    - Event processor handles encoder events (CW/CCW/press/release)
    - Command registry for extensible command system
    - Mode handlers for different menu types
"""

import time
import threading
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, Callable, List, Dict, Any
from abc import ABC, abstractmethod


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Global configuration constants"""
    DOUBLE_CLICK_MS = 300           # Double-click detection threshold
    MENU_TIMEOUT_MS = 1500          # Auto-exit menu after inactivity
    VOLUME_STEP = 2                 # Volume change percentage
    WINDOW_TITLE_MAX_LEN = 22       # Max chars for window titles
    NOTIFICATION_DURATION = 1500    # Default notification time (ms)
    COMMAND_EXECUTE_DURATION = 2000 # Command execution notification time
    ERROR_DURATION = 3000           # Error notification time


# ============================================================================
# STATE DEFINITIONS
# ============================================================================

class MenuMode(Enum):
    """Available menu modes"""
    NORMAL = auto()                 # Command selection mode

    # Main menus
    VOICEMEETER_MENU = auto()      # Voicemeeter submenu selector
    MEDIA = auto()                 # Media control mode
    VOLUME = auto()                # System volume control
    VOLUME_MIXER = auto()          # Per-app volume mixer
    RECENT_ACTIONS = auto()        # Recent action rerun list
    WINDOW_MENU = auto()           # Window manager submenu selector

    # Theme submenus
    THEME_MENU = auto()            # Theme main menu
    THEME_PRESET = auto()          # Theme presets selector
    THEME_BOX = auto()             # Box color
    THEME_ACCENT = auto()          # Accent color
    THEME_TEXT = auto()            # Text color
    THEME_GLOW = auto()            # Glow intensity/visibility

    # Voicemeeter submenus
    VM_SYSTEM = auto()             # System volume + mic mute
    VM_MIC = auto()                # Microphone Gain
    VM_MAIN_ROUTING = auto()       # Main audio routing
    VM_MUSIC_GAIN = auto()         # Music gain control
    VM_MUSIC_ROUTING = auto()      # Music routing
    VM_COMM_GAIN = auto()          # Comm gain control
    VM_COMM_ROUTING = auto()       # Comm routing

    # Window submenus
    WINDOW_CYCLE = auto()          # Alt-Tab like window switching
    WINDOW_SNAP = auto()           # Window snapping

    # App launcher menu
    APP_LAUNCHER_MENU = auto()     # App launcher submenu selector
    LIGHTING_MENU = auto()         # Lighting and SignalRGB controls
    LIGHTING_EFFECTS = auto()      # SignalRGB effect browser

    # Virtual Desktop modes (plugin)
    VIRTUAL_DESKTOP = auto()       # Virtual desktop switcher
    VIRTUAL_DESKTOP_MENU = auto()  # Virtual desktop actions menu

    # Display Control modes (plugin)
    DISPLAY_MENU = auto()          # Display control main menu
    DISPLAY_BRIGHTNESS = auto()    # Brightness adjustment
    DISPLAY_MODE = auto()          # Display mode selector
    DISPLAY_TOGGLE = auto()        # Monitor toggle

    # Context-aware modes (plugin)
    CONTEXT_MENU = auto()          # Context-specific commands

    # Integrations modes (plugin)
    INTEGRATIONS_MENU = auto()     # Integrations root menu
    INTEGRATION_DISCORD = auto()   # Discord quick actions
    INTEGRATION_OBS = auto()       # OBS quick actions
    INTEGRATION_STEAM = auto()     # Steam quick actions
    INTEGRATION_SIGNALRGB = auto() # SignalRGB quick actions


@dataclass
class AppState:
    """Application state container"""
    current_command: int = 0        # Selected command (0-3)
    previous_command: int = 0       # Previous command
    menu_mode: MenuMode = MenuMode.NORMAL
    submenu_index: int = 0          # Current submenu selection
    last_click_time: float = 0      # For double-click detection
    click_count: int = 0            # Click counter
    last_rotation_index: int = 0    # Last command index for direction detection
    routing_selection: int = 0      # For routing modes: 0=A1, 1=A2, 2=A3
    menu_timer: Optional[float] = None  # Timestamp for auto-exit
    window_list: List[Any] = None   # Cached window list

    def __post_init__(self):
        if self.window_list is None:
            self.window_list = []


# ============================================================================
# COMMAND SYSTEM
# ============================================================================

@dataclass
class Command:
    """Command definition"""
    name: str
    description: str
    action: Callable[[], None]


class CommandRegistry:
    """Registry for commands (extensible)"""

    def __init__(self):
        self.commands: List[Command] = []

    def register(self, name: str, description: str, action: Callable[[], None]) -> int:
        """Register a command and return its index"""
        cmd = Command(name=name, description=description, action=action)
        self.commands.append(cmd)
        return len(self.commands) - 1

    def get(self, index: int) -> Optional[Command]:
        """Get command by index"""
        if 0 <= index < len(self.commands):
            return self.commands[index]
        return None

    def count(self) -> int:
        """Get total number of commands"""
        return len(self.commands)


# ============================================================================
# MODE HANDLER BASE CLASS
# ============================================================================

class ModeHandler(ABC):
    """Base class for mode-specific behavior"""

    @abstractmethod
    def on_enter(self, state: AppState) -> None:
        """Called when entering this mode"""
        pass

    @abstractmethod
    def on_exit(self, state: AppState) -> None:
        """Called when exiting this mode"""
        pass

    @abstractmethod
    def on_rotation(self, state: AppState, clockwise: bool) -> None:
        """Handle rotation event"""
        pass

    @abstractmethod
    def on_press(self, state: AppState) -> None:
        """Handle press event"""
        pass

    @abstractmethod
    def get_display_text(self, state: AppState) -> Dict[str, str]:
        """Return display text for menu overlay

        Returns:
            Dict with keys: 'left', 'center', 'right' for wheel layout
        """
        pass


# ============================================================================
# STATE MACHINE
# ============================================================================

class MenuStateMachine:
    """Central state machine for menu system"""

    def __init__(self):
        self.state = AppState()
        self.commands = CommandRegistry()
        self.mode_handlers: Dict[MenuMode, ModeHandler] = {}
        self.ui_callback: Optional[Callable[[Dict[str, str]], None]] = None
        self.notification_callback: Optional[Callable[[str, int], None]] = None
        self.single_click_timer: Optional[threading.Timer] = None
        self.notifications_enabled: bool = True
        self.submenu_timeout_enabled: bool = False
        self.mode_timeout_overrides: Dict[str, int] = {}
        self.mode_parent_map: Dict[MenuMode, MenuMode] = {
            # Theme hierarchy
            MenuMode.THEME_PRESET: MenuMode.THEME_MENU,
            MenuMode.THEME_BOX: MenuMode.THEME_MENU,
            MenuMode.THEME_ACCENT: MenuMode.THEME_MENU,
            MenuMode.THEME_TEXT: MenuMode.THEME_MENU,
            MenuMode.THEME_GLOW: MenuMode.THEME_MENU,

            # Voicemeeter hierarchy
            MenuMode.VM_SYSTEM: MenuMode.VOICEMEETER_MENU,
            MenuMode.VM_MIC: MenuMode.VOICEMEETER_MENU,
            MenuMode.VM_MAIN_ROUTING: MenuMode.VOICEMEETER_MENU,
            MenuMode.VM_MUSIC_GAIN: MenuMode.VOICEMEETER_MENU,
            MenuMode.VM_MUSIC_ROUTING: MenuMode.VOICEMEETER_MENU,
            MenuMode.VM_COMM_GAIN: MenuMode.VOICEMEETER_MENU,
            MenuMode.VM_COMM_ROUTING: MenuMode.VOICEMEETER_MENU,

            # Window hierarchy
            MenuMode.WINDOW_CYCLE: MenuMode.WINDOW_MENU,
            MenuMode.WINDOW_SNAP: MenuMode.WINDOW_MENU,

            # Lighting hierarchy
            MenuMode.LIGHTING_EFFECTS: MenuMode.LIGHTING_MENU,

            # Display control hierarchy
            MenuMode.DISPLAY_BRIGHTNESS: MenuMode.DISPLAY_MENU,
            MenuMode.DISPLAY_MODE: MenuMode.DISPLAY_MENU,
            MenuMode.DISPLAY_TOGGLE: MenuMode.DISPLAY_MENU,

            # Virtual desktop hierarchy
            MenuMode.VIRTUAL_DESKTOP: MenuMode.VIRTUAL_DESKTOP_MENU,

            # Integrations hierarchy
            MenuMode.INTEGRATION_DISCORD: MenuMode.INTEGRATIONS_MENU,
            MenuMode.INTEGRATION_OBS: MenuMode.INTEGRATIONS_MENU,
            MenuMode.INTEGRATION_STEAM: MenuMode.INTEGRATIONS_MENU,
            MenuMode.INTEGRATION_SIGNALRGB: MenuMode.INTEGRATIONS_MENU,
        }

    def register_mode_handler(self, mode: MenuMode, handler: ModeHandler):
        """Register a handler for a specific mode"""
        self.mode_handlers[mode] = handler

    def set_ui_callback(self, callback: Callable[[Dict[str, str]], None]):
        """Set callback for UI updates"""
        self.ui_callback = callback

    def set_ui_hide_callback(self, callback: Callable[[], None]):
        """Set callback for hiding UI"""
        self._hide_ui = callback

    def set_notification_callback(self, callback: Callable[[str, int], None]):
        """Set callback for notifications"""
        self.notification_callback = callback

    def show_notification(self, message: str, duration: int = None):
        """Show notification via callback"""
        if self.notifications_enabled and self.notification_callback:
            self.notification_callback(message, duration or Config.NOTIFICATION_DURATION)

    def apply_settings(self, settings: Dict[str, Any]):
        """Apply runtime-tunable settings."""
        if not isinstance(settings, dict):
            return

        menu_timeout_ms = settings.get('menu_timeout_ms')
        if isinstance(menu_timeout_ms, int) and 500 <= menu_timeout_ms <= 10000:
            Config.MENU_TIMEOUT_MS = menu_timeout_ms

        double_click_ms = settings.get('double_click_ms')
        if isinstance(double_click_ms, int) and 100 <= double_click_ms <= 1000:
            Config.DOUBLE_CLICK_MS = double_click_ms

        volume_step = settings.get('volume_step')
        if isinstance(volume_step, int) and 1 <= volume_step <= 20:
            Config.VOLUME_STEP = volume_step

        notifications_enabled = settings.get('notifications_enabled')
        if isinstance(notifications_enabled, bool):
            self.notifications_enabled = notifications_enabled

        submenu_timeout_enabled = settings.get('submenu_timeout_enabled')
        if isinstance(submenu_timeout_enabled, bool):
            self.submenu_timeout_enabled = submenu_timeout_enabled

        mode_timeout_ms = settings.get('mode_timeout_ms')
        if isinstance(mode_timeout_ms, dict):
            normalized: Dict[str, int] = {}
            for key, value in mode_timeout_ms.items():
                if isinstance(key, str) and isinstance(value, int) and 500 <= value <= 15000:
                    normalized[key] = value
            self.mode_timeout_overrides = normalized

    def update_display(self):
        """Update UI display based on current state"""
        if self.state.menu_mode == MenuMode.NORMAL:
            # Show current command selection using the wheel
            if self.ui_callback:
                count = self.commands.count()
                if count > 0:
                    current = self.state.current_command
                    
                    # Calculate indices with wrapping
                    prev_idx = (current - 1) % count
                    next_idx = (current + 1) % count
                    
                    cmd_curr = self.commands.get(current)
                    cmd_prev = self.commands.get(prev_idx)
                    cmd_next = self.commands.get(next_idx)
                    
                    display = {
                        'title': 'Main Menu',
                        'center': cmd_curr.name if cmd_curr else '',
                        'left': cmd_prev.name if cmd_prev else '',
                        'right': cmd_next.name if cmd_next else '',
                        'subtitle': cmd_curr.description if cmd_curr else '',
                        'active_index': 1 # Center is active
                    }
                    self.ui_callback(display)
            
            # Legacy notification (optional, might be redundant if wheel is shown)
            # cmd = self.commands.get(self.state.current_command)
            # if cmd and self.notification_callback:
            #     self.notification_callback(cmd.name, Config.NOTIFICATION_DURATION)
        else:
            # Show menu overlay
            handler = self.mode_handlers.get(self.state.menu_mode)
            if handler and self.ui_callback:
                display = handler.get_display_text(self.state)
                self.ui_callback(display)

    def reset_menu_timer(self):
        """Reset the auto-exit timer"""
        self.state.menu_timer = time.time()

    def check_menu_timeout(self) -> bool:
        """Check if menu should auto-exit"""
        if self.state.menu_mode != MenuMode.NORMAL and not self.submenu_timeout_enabled:
            return False

        if self.state.menu_timer is None:
            return False

        elapsed = (time.time() - self.state.menu_timer) * 1000
        timeout_ms = self.mode_timeout_overrides.get(self.state.menu_mode.name, Config.MENU_TIMEOUT_MS)
        return elapsed > timeout_ms

    def enter_mode(self, mode: MenuMode):
        """Transition to a new mode"""
        # Exit current mode
        old_handler = self.mode_handlers.get(self.state.menu_mode)
        if old_handler:
            old_handler.on_exit(self.state)

        # Update state
        self.state.menu_mode = mode
        self.state.click_count = 0
        self.state.last_rotation_index = 0
        self.reset_menu_timer()

        # Enter new mode
        new_handler = self.mode_handlers.get(mode)
        if new_handler:
            new_handler.on_enter(self.state)

        # Trigger LED update if available
        if hasattr(self, 'led') and self.led:
            self.led.set_mode_color(mode.name)

        self.update_display()

    def exit_menu_mode(self):
        """Exit to normal mode"""
        if self.state.menu_mode != MenuMode.NORMAL:
            self.enter_mode(MenuMode.NORMAL)
            self.show_notification("Returned to Normal Mode", Config.NOTIFICATION_DURATION)
        else:
            # Already in NORMAL mode - just hide the UI
            self.state.menu_timer = None
            if self.ui_callback and hasattr(self, '_hide_ui'):
                self._hide_ui()
    
    def _execute_single_click(self):
        """Execute single click action after delay"""
        self.state.click_count = 0
        handler = self.mode_handlers.get(self.state.menu_mode)
        if handler:
            handler.on_press(self.state)
            self.update_display()
            self.reset_menu_timer()

    # ========================================================================
    # EVENT HANDLERS
    # ========================================================================

    def handle_rotation(self, command_index: int):
        """Handle rotation event

        Args:
            command_index: The command index (0-3) from firmware
                          Sequence determines direction (0→1→2→3→0 = CW)
        """
        if self.state.menu_mode == MenuMode.NORMAL:
            # Normal mode: Update command selection
            self.state.previous_command = self.state.current_command
            self.state.current_command = command_index
            self.update_display()
            # Reset timer in normal mode too (for auto-hide)
            self.reset_menu_timer()
        else:
            # Menu mode: Determine rotation direction and delegate to handler
            clockwise = self._is_rotating_clockwise(
                self.state.last_rotation_index,
                command_index
            )
            self.state.last_rotation_index = command_index

            handler = self.mode_handlers.get(self.state.menu_mode)
            if handler:
                handler.on_rotation(self.state, clockwise)
                self.update_display()
                self.reset_menu_timer()

    def handle_rotation_direction(self, clockwise: bool):
        """Handle rotation when direction is known directly."""
        if self.state.menu_mode == MenuMode.NORMAL:
            return

        handler = self.mode_handlers.get(self.state.menu_mode)
        if handler:
            handler.on_rotation(self.state, clockwise)
            self.update_display()
            self.reset_menu_timer()

    def handle_press(self):
        """Handle press event"""
        if self.state.menu_mode == MenuMode.NORMAL:
            # If main menu is hidden, first click should open it instead of
            # immediately executing the selected command.
            if self.state.menu_timer is None:
                self.reset_menu_timer()
                self.update_display()
                return

            # Normal mode: Execute current command
            cmd = self.commands.get(self.state.current_command)
            if cmd:
                try:
                    # Capture mode before execution
                    previous_mode = self.state.menu_mode
                    
                    cmd.action()
                    
                    # Only show notification if we stayed in NORMAL mode
                    # (i.e., it was a simple action, not a menu transition)
                    if self.state.menu_mode == previous_mode:
                        self.show_notification(f"Executed: {cmd.name}", Config.COMMAND_EXECUTE_DURATION)
                    
                    # If we changed mode, enter_mode() already called update_display()
                    
                except Exception as e:
                    self.show_notification(f"Error: {e}", Config.ERROR_DURATION)
        else:
            # Menu mode: execute immediately.
            # Double-tap exit is handled by firmware event (F18) via handle_double_tap().
            handler = self.mode_handlers.get(self.state.menu_mode)
            if handler:
                handler.on_press(self.state)
                self.update_display()
                self.reset_menu_timer()

    def handle_long_press(self):
        """Handle long press event"""
        # Could be used for alternative actions in the future
        pass

    def handle_double_tap(self):
        """Handle double tap event (from firmware)"""
        # Cancel any pending single click timer to prevent it from firing
        if self.single_click_timer:
            self.single_click_timer.cancel()
            self.single_click_timer = None
        self.go_back_one_level()

    def go_back_one_level(self):
        """Navigate one level up in menu hierarchy."""
        current = self.state.menu_mode
        if current == MenuMode.NORMAL:
            # In normal mode, treat back as hide menu overlay.
            self.exit_menu_mode()
            return

        parent = self.mode_parent_map.get(current, MenuMode.NORMAL)
        self.enter_mode(parent)
        if parent == MenuMode.NORMAL:
            self.show_notification("Returned to Normal Mode", Config.NOTIFICATION_DURATION)

    @staticmethod
    def _is_rotating_clockwise(prev_index: int, curr_index: int) -> bool:
        """Determine rotation direction from command sequence

        Normal increment: 0->1, 1->2, 2->3
        Wrap around: 3->0
        """
        if curr_index == prev_index + 1:
            return True
        if prev_index == 3 and curr_index == 0:
            return True
        return False
