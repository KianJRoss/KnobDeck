"""
Game Mode Plugin - Disable bottom two monitors

Toggles the bottom two monitors on/off for gaming.
"""

import logging
import ctypes
from ctypes import wintypes
import win32api
import win32con
import pywintypes

logger = logging.getLogger("KnobDeck.GameMode")
state_machine_ref = None

# Windows API structures and constants
class DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", ctypes.c_wchar * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmOrientation", ctypes.c_short),
        ("dmPaperSize", ctypes.c_short),
        ("dmPaperLength", ctypes.c_short),
        ("dmPaperWidth", ctypes.c_short),
        ("dmScale", ctypes.c_short),
        ("dmCopies", ctypes.c_short),
        ("dmDefaultSource", ctypes.c_short),
        ("dmPrintQuality", ctypes.c_short),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", ctypes.c_wchar * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
        ("dmPositionX", ctypes.c_long),
        ("dmPositionY", ctypes.c_long),
    ]

# Global state
game_mode_active = False
disabled_monitors = []

def get_all_monitors():
    """Get all monitor information sorted by vertical position"""
    monitors = []

    try:
        # Enumerate all display devices
        device_num = 0
        while True:
            try:
                device = win32api.EnumDisplayDevices(None, device_num, 0)
                device_name = device.DeviceName

                # Get current settings for this device
                try:
                    settings = win32api.EnumDisplaySettings(device_name, win32con.ENUM_CURRENT_SETTINGS)

                    monitor_info = {
                        'device_name': device_name,
                        'device_string': device.DeviceString,
                        'position_x': settings.Position_x,
                        'position_y': settings.Position_y,
                        'width': settings.PelsWidth,
                        'height': settings.PelsHeight,
                        'frequency': settings.DisplayFrequency,
                        'active': bool(device.StateFlags & win32con.DISPLAY_DEVICE_ACTIVE)
                    }

                    if monitor_info['active']:
                        monitors.append(monitor_info)
                        logger.info(f"Found monitor: {device.DeviceString} at ({settings.Position_x}, {settings.Position_y})")

                except pywintypes.error:
                    # No settings available for this device
                    pass

                device_num += 1

            except pywintypes.error:
                # No more devices
                break

        # Sort by Y position (highest Y = bottom monitors)
        monitors.sort(key=lambda m: m['position_y'], reverse=True)

    except Exception as e:
        logger.error(f"Error enumerating monitors: {e}")

    return monitors

def disable_monitor(device_name):
    """Disable a specific monitor"""
    try:
        # Get current settings
        devmode = win32api.EnumDisplaySettings(device_name, win32con.ENUM_CURRENT_SETTINGS)

        # Store original settings
        original_settings = {
            'device_name': device_name,
            'position_x': devmode.Position_x,
            'position_y': devmode.Position_y,
            'width': devmode.PelsWidth,
            'height': devmode.PelsHeight,
            'frequency': devmode.DisplayFrequency,
            'bits_per_pel': devmode.BitsPerPel
        }

        # Create new devmode with position set to disable
        devmode.PelsWidth = 0
        devmode.PelsHeight = 0
        devmode.Fields = win32con.DM_PELSWIDTH | win32con.DM_PELSHEIGHT | win32con.DM_POSITION

        # Apply the change
        result = win32api.ChangeDisplaySettingsEx(device_name, devmode, win32con.CDS_UPDATEREGISTRY)

        if result == win32con.DISP_CHANGE_SUCCESSFUL:
            logger.info(f"Disabled monitor: {device_name}")
            return original_settings
        else:
            logger.error(f"Failed to disable monitor: {device_name}, result: {result}")
            return None

    except Exception as e:
        logger.error(f"Error disabling monitor {device_name}: {e}")
        return None

def enable_monitor(settings):
    """Re-enable a monitor with its original settings"""
    try:
        device_name = settings['device_name']

        # Get a fresh devmode structure
        devmode = win32api.EnumDisplaySettings(device_name, win32con.ENUM_REGISTRY_SETTINGS)

        # Restore original settings
        devmode.PelsWidth = settings['width']
        devmode.PelsHeight = settings['height']
        devmode.Position_x = settings['position_x']
        devmode.Position_y = settings['position_y']
        devmode.DisplayFrequency = settings['frequency']
        devmode.BitsPerPel = settings['bits_per_pel']
        devmode.Fields = (win32con.DM_PELSWIDTH | win32con.DM_PELSHEIGHT |
                         win32con.DM_POSITION | win32con.DM_DISPLAYFREQUENCY |
                         win32con.DM_BITSPERPEL)

        # Apply the change
        result = win32api.ChangeDisplaySettingsEx(device_name, devmode, win32con.CDS_UPDATEREGISTRY)

        if result == win32con.DISP_CHANGE_SUCCESSFUL:
            logger.info(f"Re-enabled monitor: {device_name}")
            return True
        else:
            logger.error(f"Failed to re-enable monitor: {device_name}, result: {result}")
            return False

    except Exception as e:
        logger.error(f"Error enabling monitor {device_name}: {e}")
        return False

def toggle_game_mode():
    """Toggle game mode - disable/enable bottom two monitors"""
    global game_mode_active, disabled_monitors

    if game_mode_active:
        # Re-enable monitors
        logger.info("Exiting game mode - re-enabling monitors...")
        for settings in disabled_monitors:
            enable_monitor(settings)
        disabled_monitors = []
        game_mode_active = False
        logger.info("Game mode OFF")
        return "Game Mode OFF: all disabled monitors restored"
    else:
        # Disable bottom two monitors
        logger.info("Entering game mode - disabling bottom two monitors...")
        monitors = get_all_monitors()

        if len(monitors) <= 2:
            logger.warning("Not enough monitors to enable game mode (need at least 3)")
            return "Game Mode unavailable: need at least 3 active monitors"

        # Disable the bottom two (first two after sorting by Y position descending)
        disabled_monitors = []
        for i in range(min(2, len(monitors))):
            monitor = monitors[i]
            logger.info(f"Disabling: {monitor['device_string']}")
            settings = disable_monitor(monitor['device_name'])
            if settings:
                disabled_monitors.append(settings)

        if disabled_monitors:
            game_mode_active = True
            logger.info("Game mode ON")
            return f"Game Mode ON: disabled {len(disabled_monitors)} bottom monitor(s)"
        else:
            logger.error("Failed to disable any monitors")
            return "Game Mode failed: no monitors were disabled"


def get_game_mode_state() -> str:
    return "ON" if game_mode_active else "OFF"

# Plugin interface
def get_commands():
    """Return commands to register with the menu system"""
    return [
        {
            "name": "Game Mode",
            "description": "Disable bottom monitors for gaming (status shown in notification)",
            "callback": _toggle_game_mode_with_feedback
        }
    ]


def _toggle_game_mode_with_feedback():
    global state_machine_ref
    message = toggle_game_mode()
    if state_machine_ref is not None:
        state_machine_ref.show_notification(message, 1800)
    return message


def get_mode_handlers(state_machine):
    global state_machine_ref
    state_machine_ref = state_machine
    return {}
