"""
Virtual Desktop Switcher Plugin
Allows switching between Windows 10/11 virtual desktops using the encoder
"""

import logging
import ctypes
from ctypes import wintypes
import win32gui
import win32process
import win32con

logger = logging.getLogger("KnobDeck.VirtualDesktops")

# Windows 10+ Virtual Desktop COM interfaces
# We'll use a simpler approach with keyboard shortcuts since COM is complex

class VirtualDesktopManager:
    """Manage Windows Virtual Desktops"""

    def __init__(self):
        self.current_desktop_index = 0
        self.desktop_count = self._estimate_desktop_count()

    def _estimate_desktop_count(self):
        """Estimate number of desktops (Windows doesn't expose this easily)"""
        # Default to 4 as a reasonable estimate
        return 4

    def switch_next(self):
        """Switch to next virtual desktop"""
        try:
            # Windows shortcut: Win+Ctrl+Right
            import win32api
            import win32con
            import time

            # Press Win+Ctrl+Right
            win32api.keybd_event(win32con.VK_LWIN, 0, 0, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(win32con.VK_RIGHT, 0, 0, 0)
            time.sleep(0.02)
            win32api.keybd_event(win32con.VK_RIGHT, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_LWIN, 0, win32con.KEYEVENTF_KEYUP, 0)

            self.current_desktop_index = (self.current_desktop_index + 1) % self.desktop_count
            logger.info("Switched to next desktop")
            return True
        except Exception as e:
            logger.error(f"Failed to switch desktop: {e}")
            return False

    def switch_previous(self):
        """Switch to previous virtual desktop"""
        try:
            import win32api
            import win32con
            import time

            # Press Win+Ctrl+Left
            win32api.keybd_event(win32con.VK_LWIN, 0, 0, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(win32con.VK_LEFT, 0, 0, 0)
            time.sleep(0.02)
            win32api.keybd_event(win32con.VK_LEFT, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_LWIN, 0, win32con.KEYEVENTF_KEYUP, 0)

            self.current_desktop_index = (self.current_desktop_index - 1) % self.desktop_count
            logger.info("Switched to previous desktop")
            return True
        except Exception as e:
            logger.error(f"Failed to switch desktop: {e}")
            return False

    def move_window_to_next_desktop(self):
        """Move active window to next desktop"""
        try:
            import win32api
            import win32con
            import time

            # Press Win+Ctrl+Shift+Right
            win32api.keybd_event(win32con.VK_LWIN, 0, 0, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
            win32api.keybd_event(win32con.VK_RIGHT, 0, 0, 0)
            time.sleep(0.02)
            win32api.keybd_event(win32con.VK_RIGHT, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_LWIN, 0, win32con.KEYEVENTF_KEYUP, 0)

            logger.info("Moved window to next desktop")
            return "Window moved →"
        except Exception as e:
            logger.error(f"Failed to move window: {e}")
            return f"Error: {e}"

    def move_window_to_previous_desktop(self):
        """Move active window to previous desktop"""
        try:
            import win32api
            import win32con
            import time

            # Press Win+Ctrl+Shift+Left
            win32api.keybd_event(win32con.VK_LWIN, 0, 0, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
            win32api.keybd_event(win32con.VK_LEFT, 0, 0, 0)
            time.sleep(0.02)
            win32api.keybd_event(win32con.VK_LEFT, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_LWIN, 0, win32con.KEYEVENTF_KEYUP, 0)

            logger.info("Moved window to previous desktop")
            return "Window moved ←"
        except Exception as e:
            logger.error(f"Failed to move window: {e}")
            return f"Error: {e}"

    def create_new_desktop(self):
        """Create a new virtual desktop"""
        try:
            import win32api
            import win32con
            import time

            # Press Win+Ctrl+D
            win32api.keybd_event(win32con.VK_LWIN, 0, 0, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(0x44, 0, 0, 0)  # D key
            time.sleep(0.02)
            win32api.keybd_event(0x44, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_LWIN, 0, win32con.KEYEVENTF_KEYUP, 0)

            self.desktop_count += 1
            logger.info("Created new desktop")
            return "New desktop created"
        except Exception as e:
            logger.error(f"Failed to create desktop: {e}")
            return f"Error: {e}"

    def close_current_desktop(self):
        """Close the current virtual desktop"""
        try:
            import win32api
            import win32con
            import time

            # Press Win+Ctrl+F4
            win32api.keybd_event(win32con.VK_LWIN, 0, 0, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(win32con.VK_F4, 0, 0, 0)
            time.sleep(0.02)
            win32api.keybd_event(win32con.VK_F4, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_LWIN, 0, win32con.KEYEVENTF_KEYUP, 0)

            if self.desktop_count > 1:
                self.desktop_count -= 1
            logger.info("Closed current desktop")
            return "Desktop closed"
        except Exception as e:
            logger.error(f"Failed to close desktop: {e}")
            return f"Error: {e}"


# Global instance
_vd_manager = VirtualDesktopManager()
_state_machine = None  # Will be set when plugin loads


# Mode handler
from menu_system import ModeHandler, AppState, MenuMode
from typing import Dict

class VirtualDesktopSwitchHandler(ModeHandler):
    """Switch between virtual desktops"""

    def __init__(self, state_machine):
        self.sm = state_machine
        self.manager = _vd_manager

    def on_enter(self, state: AppState):
        pass

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        """Rotate: Switch desktops"""
        if clockwise:
            self.manager.switch_next()
        else:
            self.manager.switch_previous()

    def on_press(self, state: AppState):
        """Press: Show submenu"""
        self.sm.enter_mode(MenuMode.VIRTUAL_DESKTOP_MENU)

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        return {
            'left': '← Previous',
            'center': 'Desktop Options',
            'right': 'Next →',
            'title': '🖥️ Virtual Desktops',
            'subtitle': 'Press for options',
            'icons': {'left': '←', 'center': '▼', 'right': '→'}
        }


class VirtualDesktopMenuHandler(ModeHandler):
    """Virtual Desktop submenu"""

    def __init__(self, state_machine):
        self.sm = state_machine
        self.manager = _vd_manager
        self.options = [
            {'name': 'Move Window →', 'action': 'move_next'},
            {'name': 'Move Window ←', 'action': 'move_prev'},
            {'name': 'New Desktop', 'action': 'create'},
            {'name': 'Close Desktop', 'action': 'close'},
        ]

    def on_enter(self, state: AppState):
        state.submenu_index = 0

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        """Rotate: Select option"""
        if clockwise:
            state.submenu_index = (state.submenu_index + 1) % len(self.options)
        else:
            state.submenu_index = (state.submenu_index - 1) % len(self.options)

    def on_press(self, state: AppState):
        """Press: Execute action"""
        option = self.options[state.submenu_index]
        action = option['action']

        result = None
        if action == 'move_next':
            result = self.manager.move_window_to_next_desktop()
        elif action == 'move_prev':
            result = self.manager.move_window_to_previous_desktop()
        elif action == 'create':
            result = self.manager.create_new_desktop()
        elif action == 'close':
            result = self.manager.close_current_desktop()

        if result:
            self.sm.show_notification(result, 2000)

        # Return to main virtual desktop mode
        self.sm.enter_mode(MenuMode.VIRTUAL_DESKTOP)

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        total = len(self.options)
        prev_idx = (state.submenu_index - 1) % total
        next_idx = (state.submenu_index + 1) % total

        return {
            'left': self.options[prev_idx]['name'],
            'center': f"▶ {self.options[state.submenu_index]['name']}",
            'right': self.options[next_idx]['name'],
            'title': '🖥️ Desktop Actions'
        }


# Plugin interface
def get_commands():
    """Return commands to register"""
    return [
        {
            "name": "Virtual Desktops",
            "description": "Switch between Windows virtual desktops",
            "callback": _enter_virtual_desktop_mode
        }
    ]

def get_mode_handlers(state_machine):
    """Return mode handlers"""
    global _state_machine
    _state_machine = state_machine

    return {
        MenuMode.VIRTUAL_DESKTOP: VirtualDesktopSwitchHandler(state_machine),
        MenuMode.VIRTUAL_DESKTOP_MENU: VirtualDesktopMenuHandler(state_machine)
    }

def _enter_virtual_desktop_mode():
    """Enter virtual desktop mode"""
    if _state_machine:
        _state_machine.enter_mode(MenuMode.VIRTUAL_DESKTOP)
