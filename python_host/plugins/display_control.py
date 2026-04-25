"""
Display Control Plugin
Enhanced monitor management with brightness, display modes, and more
"""

import logging
import ctypes
from ctypes import wintypes
import win32api
import win32con
import pywintypes
import subprocess

logger = logging.getLogger("KnobDeck.DisplayControl")

# Windows display device state flags (not all defined in win32con)
DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x00000001
DISPLAY_DEVICE_PRIMARY_DEVICE = 0x00000004
DISPLAY_DEVICE_ACTIVE = 0x00000001  # Same as ATTACHED_TO_DESKTOP

# Windows API for monitor brightness (DDC/CI)
class PHYSICAL_MONITOR(ctypes.Structure):
    _fields_ = [('hPhysicalMonitor', wintypes.HANDLE),
                ('szPhysicalMonitorDescription', wintypes.WCHAR * 128)]

# Load required DLLs
try:
    dxva2 = ctypes.windll.dxva2
    user32 = ctypes.windll.user32
    shcore = ctypes.windll.shcore
except:
    dxva2 = None
    user32 = None
    shcore = None


class DisplayManager:
    """Manage display settings"""

    def __init__(self):
        self.monitors = []
        self.current_brightness = None  # Will be read on first use
        self.saved_settings = {}  # Store original settings for disabled monitors
        self._enumerate_monitors()
        self._read_current_brightness()

    def _enumerate_monitors(self):
        """Get list of all monitors"""
        try:
            self.monitors = []
            device_num = 0
            logger.info("Enumerating display devices...")

            while True:
                try:
                    device = win32api.EnumDisplayDevices(None, device_num, 0)
                    device_name = device.DeviceName

                    logger.info(f"Device {device_num}: {device_name}, Flags: {device.StateFlags} (0x{device.StateFlags:08X})")

                    # Check if device is attached
                    is_attached = bool(device.StateFlags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP)
                    is_active = bool(device.StateFlags & DISPLAY_DEVICE_ACTIVE)

                    if is_attached:
                        try:
                            settings = win32api.EnumDisplaySettings(device_name, win32con.ENUM_CURRENT_SETTINGS)

                            # Create friendly name with resolution
                            resolution = f"{settings.PelsWidth}x{settings.PelsHeight}"
                            friendly_name = f"Display {device_num + 1} ({resolution})"

                            monitor_info = {
                                'device_name': device_name,
                                'device_string': device.DeviceString,
                                'friendly_name': friendly_name,
                                'display_number': device_num + 1,
                                'position_x': settings.Position_x,
                                'position_y': settings.Position_y,
                                'width': settings.PelsWidth,
                                'height': settings.PelsHeight,
                                'frequency': settings.DisplayFrequency,
                                'bits_per_pel': settings.BitsPerPel,
                                'active': is_active,
                                'is_primary': bool(device.StateFlags & DISPLAY_DEVICE_PRIMARY_DEVICE)
                            }

                            self.monitors.append(monitor_info)
                            status = "ACTIVE" if is_active else "INACTIVE"
                            primary = " [PRIMARY]" if monitor_info['is_primary'] else ""
                            logger.info(f"  -> Found monitor [{status}]: {friendly_name}{primary}")

                        except pywintypes.error as e:
                            logger.warning(f"  -> Could not get settings for {device_name}: {e}")

                    device_num += 1

                except pywintypes.error:
                    break

            logger.info(f"Total monitors found: {len(self.monitors)}")

        except Exception as e:
            logger.error(f"Error enumerating monitors: {e}")

    def get_monitor_count(self):
        """Get number of active monitors"""
        return len(self.monitors)

    def _read_current_brightness(self):
        """Read current brightness from WMI"""
        try:
            ps_command = "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"
            result = subprocess.run(["powershell", "-Command", ps_command],
                                  capture_output=True, timeout=2, text=True)

            if result.returncode == 0 and result.stdout.strip():
                brightness = int(result.stdout.strip())
                self.current_brightness = brightness
                logger.info(f"Current brightness: {brightness}%")
            else:
                logger.warning(f"Could not read brightness, using default 50%")
                self.current_brightness = 50
        except Exception as e:
            logger.warning(f"Failed to read brightness: {e}, using default 50%")
            self.current_brightness = 50

    def get_brightness(self, monitor_index=0):
        """Get monitor brightness (0-100)"""
        if self.current_brightness is None:
            self._read_current_brightness()
        return self.current_brightness

    def set_brightness(self, brightness, monitor_index=0):
        """Set monitor brightness (0-100)"""
        try:
            brightness = max(0, min(100, brightness))

            ps_command = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{brightness})"
            result = subprocess.run(["powershell", "-Command", ps_command],
                                  capture_output=True, timeout=2, text=True)

            if result.returncode == 0:
                self.current_brightness = brightness
                logger.info(f"Set brightness to {brightness}%")
                return True
            else:
                logger.error(f"Failed to set brightness: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Failed to set brightness: {e}")
            return False

    def adjust_brightness(self, delta, monitor_index=0):
        """Adjust brightness by delta"""
        current = self.get_brightness(monitor_index)
        new_brightness = max(0, min(100, current + delta))
        success = self.set_brightness(new_brightness, monitor_index)

        if not success:
            # If WMI failed, might not be supported
            logger.warning("Brightness control not supported on this system")

        return success

    def cycle_display_mode(self):
        """Cycle through display modes (Win+P)"""
        try:
            import win32api
            import win32con
            import time

            # Press Win+P
            win32api.keybd_event(win32con.VK_LWIN, 0, 0, 0)
            win32api.keybd_event(0x50, 0, 0, 0)  # P key
            time.sleep(0.02)
            win32api.keybd_event(0x50, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_LWIN, 0, win32con.KEYEVENTF_KEYUP, 0)

            logger.info("Opened display mode selector")
            return "Display modes"
        except Exception as e:
            logger.error(f"Failed to cycle display mode: {e}")
            return f"Error: {e}"

    def set_display_mode(self, mode):
        """Set display mode

        Args:
            mode: 'pc', 'duplicate', 'extend', or 'second'
        """
        try:
            # Open Win+P menu
            import win32api
            import win32con
            import time

            win32api.keybd_event(win32con.VK_LWIN, 0, 0, 0)
            win32api.keybd_event(0x50, 0, 0, 0)  # P key
            time.sleep(0.05)
            win32api.keybd_event(0x50, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_LWIN, 0, win32con.KEYEVENTF_KEYUP, 0)

            time.sleep(0.3)  # Wait for menu to appear

            # Navigate to correct option
            mode_keys = {
                'pc': 0,        # PC screen only
                'duplicate': 1, # Duplicate
                'extend': 2,    # Extend
                'second': 3     # Second screen only
            }

            presses = mode_keys.get(mode, 0)
            for _ in range(presses):
                win32api.keybd_event(win32con.VK_DOWN, 0, 0, 0)
                time.sleep(0.05)
                win32api.keybd_event(win32con.VK_DOWN, 0, win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.05)

            # Press Enter to confirm
            win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
            time.sleep(0.02)
            win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)

            mode_names = {
                'pc': 'PC only',
                'duplicate': 'Duplicate',
                'extend': 'Extend',
                'second': 'Second only'
            }
            logger.info(f"Set display mode to: {mode_names.get(mode, mode)}")
            return f"Mode: {mode_names.get(mode, mode)}"
        except Exception as e:
            logger.error(f"Failed to set display mode: {e}")
            return f"Error: {e}"

    def toggle_monitor(self, monitor_index):
        """Toggle monitor on/off"""
        if monitor_index >= len(self.monitors):
            return "Monitor not found"

        monitor = self.monitors[monitor_index]
        device_name = monitor['device_name']

        # Safety: Don't allow disabling primary monitor
        if monitor['is_primary']:
            return "Cannot disable primary monitor"

        try:
            if monitor['active']:
                # DISABLE: Save current settings first
                logger.info(f"Disabling monitor: {monitor['friendly_name']}")

                # Get current settings
                devmode = win32api.EnumDisplaySettings(device_name, win32con.ENUM_CURRENT_SETTINGS)

                # Save full settings
                self.saved_settings[device_name] = {
                    'width': devmode.PelsWidth,
                    'height': devmode.PelsHeight,
                    'position_x': devmode.Position_x,
                    'position_y': devmode.Position_y,
                    'frequency': devmode.DisplayFrequency,
                    'bits_per_pel': devmode.BitsPerPel
                }
                logger.info(f"  Saved settings: {self.saved_settings[device_name]}")

                # Disable by setting resolution to 0
                devmode.PelsWidth = 0
                devmode.PelsHeight = 0
                devmode.Fields = win32con.DM_PELSWIDTH | win32con.DM_PELSHEIGHT | win32con.DM_POSITION

                # Apply the change (single call, like game_mode.py)
                result = win32api.ChangeDisplaySettingsEx(device_name, devmode, win32con.CDS_UPDATEREGISTRY)

                if result == win32con.DISP_CHANGE_SUCCESSFUL:
                    monitor['active'] = False
                    logger.info(f"  Successfully disabled")

                    # Refresh to update state
                    import time
                    time.sleep(0.2)
                    self._enumerate_monitors()

                    return f"✓ Disabled {monitor['friendly_name']}"
                else:
                    logger.error(f"  Failed with result: {result}")
                    return f"Failed to disable (error {result})"

            else:
                # RE-ENABLE: Restore saved settings
                logger.info(f"Re-enabling monitor: {monitor['friendly_name']}")

                if device_name not in self.saved_settings:
                    logger.error(f"  No saved settings found!")
                    return "No saved settings (restart app)"

                saved = self.saved_settings[device_name]
                logger.info(f"  Restoring settings: {saved}")

                # Get a fresh devmode structure
                devmode = win32api.EnumDisplaySettings(device_name, win32con.ENUM_REGISTRY_SETTINGS)

                # Restore original settings
                devmode.PelsWidth = saved['width']
                devmode.PelsHeight = saved['height']
                devmode.Position_x = saved['position_x']
                devmode.Position_y = saved['position_y']
                devmode.DisplayFrequency = saved['frequency']
                devmode.BitsPerPel = saved['bits_per_pel']
                devmode.Fields = (win32con.DM_PELSWIDTH | win32con.DM_PELSHEIGHT |
                                win32con.DM_POSITION | win32con.DM_DISPLAYFREQUENCY |
                                win32con.DM_BITSPERPEL)

                # Apply the change (single call, like game_mode.py)
                result = win32api.ChangeDisplaySettingsEx(device_name, devmode, win32con.CDS_UPDATEREGISTRY)

                if result == win32con.DISP_CHANGE_SUCCESSFUL:
                    monitor['active'] = True
                    logger.info(f"  Successfully re-enabled")

                    # Refresh monitor list to get updated status
                    import time
                    time.sleep(0.2)
                    self._enumerate_monitors()

                    return f"✓ Enabled {monitor['friendly_name']}"
                else:
                    logger.error(f"  Failed with result: {result}")
                    return f"Failed to enable (error {result})"

        except Exception as e:
            logger.error(f"Error toggling monitor: {e}", exc_info=True)
            return f"Error: {str(e)[:30]}"


# Global instance (will be initialized when plugin loads)
_display_manager = None
_state_machine = None


# Mode handlers
from menu_system import ModeHandler, AppState, MenuMode
from typing import Dict

class DisplayControlMenuHandler(ModeHandler):
    """Display control submenu"""

    def __init__(self, state_machine, manager):
        self.sm = state_machine
        self.manager = manager
        self.submenus = [
            {'name': 'Brightness', 'mode': MenuMode.DISPLAY_BRIGHTNESS},
            {'name': 'Display Mode', 'mode': MenuMode.DISPLAY_MODE},
            {'name': 'Toggle Monitor', 'mode': MenuMode.DISPLAY_TOGGLE},
        ]

    def on_enter(self, state: AppState):
        state.submenu_index = 0

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        """Rotate: Select submenu"""
        if clockwise:
            state.submenu_index = (state.submenu_index + 1) % len(self.submenus)
        else:
            state.submenu_index = (state.submenu_index - 1) % len(self.submenus)

    def on_press(self, state: AppState):
        """Press: Enter submenu"""
        submenu = self.submenus[state.submenu_index]
        self.sm.enter_mode(submenu['mode'])

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        total = len(self.submenus)
        prev_idx = (state.submenu_index - 1) % total
        next_idx = (state.submenu_index + 1) % total

        return {
            'left': self.submenus[prev_idx]['name'],
            'center': f"▶ {self.submenus[state.submenu_index]['name']}",
            'right': self.submenus[next_idx]['name'],
            'title': '🖥️ Display Control'
        }


class BrightnessControlHandler(ModeHandler):
    """Brightness adjustment"""

    def __init__(self, manager):
        self.manager = manager
        self.step = 5

    def on_enter(self, state: AppState):
        # Refresh current brightness reading
        self.manager._read_current_brightness()

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        """Rotate: Adjust brightness"""
        delta = self.step if clockwise else -self.step
        self.manager.adjust_brightness(delta)

    def on_press(self, state: AppState):
        """Press: Reset to 50%"""
        self.manager.set_brightness(50)

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        brightness = self.manager.get_brightness()

        return {
            'left': 'Dimmer',
            'center': f'{brightness}%',
            'right': 'Brighter',
            'title': '☀️ Brightness',
            'progress': brightness / 100.0,
            'icons': {'left': '−', 'center': '☀️', 'right': '+'}
        }


class DisplayModeHandler(ModeHandler):
    """Display mode selector"""

    def __init__(self, state_machine, manager):
        self.sm = state_machine
        self.manager = manager
        self.modes = [
            {'name': '🖥️ PC Only', 'key': 'pc'},
            {'name': '👥 Duplicate', 'key': 'duplicate'},
            {'name': '🔗 Extend', 'key': 'extend'},
            {'name': '📺 Second Only', 'key': 'second'},
        ]

    def on_enter(self, state: AppState):
        state.submenu_index = 2  # Start at Extend (most common)

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        """Rotate: Select mode"""
        if clockwise:
            state.submenu_index = (state.submenu_index + 1) % len(self.modes)
        else:
            state.submenu_index = (state.submenu_index - 1) % len(self.modes)

    def on_press(self, state: AppState):
        """Press: Apply mode and exit"""
        mode = self.modes[state.submenu_index]
        result = self.manager.set_display_mode(mode['key'])
        self.sm.show_notification(result, 2000)
        self.sm.exit_menu_mode()

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        total = len(self.modes)
        prev_idx = (state.submenu_index - 1) % total
        next_idx = (state.submenu_index + 1) % total

        return {
            'left': self.modes[prev_idx]['name'],
            'center': f"▶ {self.modes[state.submenu_index]['name']}",
            'right': self.modes[next_idx]['name'],
            'title': '🖥️ Display Mode'
        }


class MonitorToggleHandler(ModeHandler):
    """Toggle individual monitors"""

    def __init__(self, state_machine, manager):
        self.sm = state_machine
        self.manager = manager

    def on_enter(self, state: AppState):
        # Refresh monitor list
        self.manager._enumerate_monitors()

        # Initialize to first non-primary monitor if possible
        state.submenu_index = 0
        for i, mon in enumerate(self.manager.monitors):
            if not mon['is_primary']:
                state.submenu_index = i
                break

        logger.info(f"Entered monitor toggle, starting at index {state.submenu_index}")

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        """Rotate: Select monitor"""
        monitor_count = self.manager.get_monitor_count()
        if monitor_count == 0:
            return

        old_index = state.submenu_index

        if clockwise:
            state.submenu_index = (state.submenu_index + 1) % monitor_count
        else:
            state.submenu_index = (state.submenu_index - 1) % monitor_count

        logger.info(f"Rotated from monitor {old_index} to {state.submenu_index}")

    def on_press(self, state: AppState):
        """Press: Toggle selected monitor"""
        monitor = self.manager.monitors[state.submenu_index]
        logger.info(f"Toggling monitor {state.submenu_index}: {monitor['friendly_name']}")

        result = self.manager.toggle_monitor(state.submenu_index)
        self.sm.show_notification(result, 3000)

        # Refresh the display after toggle
        self.sm.update_display()

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        monitors = self.manager.monitors
        if not monitors:
            return {
                'left': '',
                'center': 'No monitors found',
                'right': '',
                'title': '⚠️ Error'
            }

        if len(monitors) == 1:
            mon = monitors[0]
            status = "ON" if mon['active'] else "OFF"
            primary = " [PRIMARY]" if mon['is_primary'] else ""
            return {
                'left': '',
                'center': f"{mon['friendly_name']} [{status}]{primary}",
                'right': '',
                'title': '🖥️ Toggle Monitor',
                'subtitle': 'Press to toggle' if not mon['is_primary'] else 'Primary cannot be disabled'
            }

        # Multiple monitors
        total = len(monitors)
        prev_idx = (state.submenu_index - 1) % total
        next_idx = (state.submenu_index + 1) % total

        prev_mon = monitors[prev_idx]
        curr_mon = monitors[state.submenu_index]
        next_mon = monitors[next_idx]

        status = "ON" if curr_mon['active'] else "OFF"
        primary_mark = " ★" if curr_mon['is_primary'] else ""

        # Show just the display number and resolution
        prev_text = f"D{prev_mon['display_number']}"
        curr_text = f"D{curr_mon['display_number']} [{status}]{primary_mark}"
        next_text = f"D{next_mon['display_number']}"

        return {
            'left': prev_text,
            'center': f"▶ {curr_text}",
            'right': next_text,
            'title': f"🖥️ {curr_mon['friendly_name']}",
            'subtitle': 'Press to toggle' if not curr_mon['is_primary'] else '★ Primary (cannot disable)'
        }


# Plugin interface
def get_commands():
    """Return commands to register"""
    return [
        {
            "name": "Display Control",
            "description": "Brightness, display modes, monitor toggle",
            "callback": _enter_display_menu
        }
    ]

def get_mode_handlers(state_machine):
    """Return mode handlers"""
    global _state_machine, _display_manager
    _state_machine = state_machine

    # Initialize display manager now (after logging is set up)
    if _display_manager is None:
        logger.info("Initializing Display Manager...")
        _display_manager = DisplayManager()
        logger.info(f"Display Manager initialized with {_display_manager.get_monitor_count()} monitor(s)")

    return {
        MenuMode.DISPLAY_MENU: DisplayControlMenuHandler(state_machine, _display_manager),
        MenuMode.DISPLAY_BRIGHTNESS: BrightnessControlHandler(_display_manager),
        MenuMode.DISPLAY_MODE: DisplayModeHandler(state_machine, _display_manager),
        MenuMode.DISPLAY_TOGGLE: MonitorToggleHandler(state_machine, _display_manager),
    }

def _enter_display_menu():
    """Enter display control menu"""
    if _state_machine:
        _state_machine.enter_mode(MenuMode.DISPLAY_MENU)
