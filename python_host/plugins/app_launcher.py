"""
App Launcher Plugin for KnobDeck

Provides an "Apps" menu with Cursor, Playnite, and Opera GX launchers
"""

import subprocess
import os
import logging
import sys
from typing import Dict, Any

# Import parent directory modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from menu_system import MenuMode, AppState, ModeHandler

logger = logging.getLogger("KnobDeck.AppLauncher")

# ============================================================================
# APPLICATION PATHS
# ============================================================================

USERNAME = os.environ.get('USERNAME', 'YourUsername')
LOCALAPPDATA = os.environ.get('LOCALAPPDATA', f'C:\\Users\\{USERNAME}\\AppData\\Local')

APP_PATHS = {
    "cursor": r"C:\Program Files\cursor\Cursor.exe",
    "playnite": os.path.join(LOCALAPPDATA, r"Playnite\Playnite.FullscreenApp.exe"),
    "operagx": os.path.join(LOCALAPPDATA, r"Programs\Opera GX\launcher.exe")
}

# Alternative paths to try
ALT_PATHS = {
    "cursor": [
        os.path.join(LOCALAPPDATA, r"Programs\cursor\Cursor.exe"),
        r"C:\Program Files (x86)\Cursor\Cursor.exe"
    ],
    "playnite": [
        r"C:\Program Files\Playnite\Playnite.FullscreenApp.exe",
        r"C:\Program Files (x86)\Playnite\Playnite.FullscreenApp.exe",
        r"D:\Program Files\Playnite\Playnite.FullscreenApp.exe"
    ],
    "operagx": [
        r"C:\Program Files\Opera GX\launcher.exe",
        r"C:\Program Files (x86)\Opera GX\launcher.exe"
    ]
}


# ============================================================================
# LAUNCHER FUNCTIONS
# ============================================================================

def find_app_path(app_key):
    """Find the correct path for an application by checking main and alternative paths"""
    # Try main path first
    main_path = APP_PATHS.get(app_key)
    if main_path and os.path.exists(main_path):
        logger.info(f"Found {app_key} at: {main_path}")
        return main_path

    # Try alternative paths
    for alt_path in ALT_PATHS.get(app_key, []):
        if os.path.exists(alt_path):
            logger.info(f"Found {app_key} at alternate location: {alt_path}")
            return alt_path

    # Log where we searched
    logger.warning(f"Could not find {app_key}. Searched:")
    logger.warning(f"  Main: {main_path}")
    for alt_path in ALT_PATHS.get(app_key, []):
        logger.warning(f"  Alt: {alt_path}")

    return None


def launch_cursor():
    """Launch Cursor editor"""
    path = find_app_path("cursor")

    if not path:
        logger.error("Cursor not found! Please update the path in plugins/app_launcher.py")
        return

    try:
        subprocess.Popen([path], shell=True)
        logger.info(f"Launching Cursor from: {path}")
    except Exception as e:
        logger.error(f"Failed to launch Cursor: {e}")


def launch_playnite():
    """Launch Playnite in fullscreen mode with admin privileges"""
    path = find_app_path("playnite")

    if not path:
        logger.error("Playnite not found! Please update the path in plugins/app_launcher.py")
        return

    try:
        # Launch with admin rights using PowerShell
        powershell_cmd = f'Start-Process -FilePath "{path}" -Verb RunAs -ArgumentList "--mode", "fullscreen"'
        subprocess.Popen(['powershell', '-Command', powershell_cmd], shell=True)
        logger.info(f"Launching Playnite (admin) from: {path}")
    except Exception as e:
        logger.error(f"Failed to launch Playnite: {e}")


def launch_operagx():
    """Launch Opera GX browser"""
    path = find_app_path("operagx")

    if not path:
        logger.error("Opera GX not found! Please update the path in plugins/app_launcher.py")
        return

    try:
        subprocess.Popen([path], shell=True)
        logger.info(f"Launching Opera GX from: {path}")
    except Exception as e:
        logger.error(f"Failed to launch Opera GX: {e}")


# ============================================================================
# APP LAUNCHER MENU HANDLER
# ============================================================================

class AppLauncherMenuHandler(ModeHandler):
    """App launcher submenu selector"""

    def __init__(self, state_machine):
        self.sm = state_machine
        self.submenus = [
            {'name': 'Cursor', 'action': launch_cursor},
            {'name': 'Playnite', 'action': launch_playnite},
            {'name': 'Opera GX', 'action': launch_operagx}
        ]

    def on_enter(self, state: AppState):
        state.submenu_index = 0

    def on_exit(self, state: AppState):
        pass

    def on_rotation(self, state: AppState, clockwise: bool):
        """Rotate: Cycle through apps"""
        if clockwise:
            state.submenu_index = (state.submenu_index + 1) % len(self.submenus)
        else:
            state.submenu_index = (state.submenu_index - 1) % len(self.submenus)

    def on_press(self, state: AppState):
        """Press: Launch selected app"""
        submenu = self.submenus[state.submenu_index]
        if 'action' in submenu:
            # Execute action
            submenu['action']()
            self.sm.exit_menu_mode()

    def get_display_text(self, state: AppState) -> Dict[str, str]:
        total = len(self.submenus)
        prev_idx = (state.submenu_index - 1) % total
        next_idx = (state.submenu_index + 1) % total

        return {
            'title': '🚀 Apps',
            'left': self.submenus[prev_idx]['name'],
            'center': f"▶ {self.submenus[state.submenu_index]['name']}",
            'right': self.submenus[next_idx]['name']
        }


# ============================================================================
# PLUGIN INTERFACE
# ============================================================================

def get_commands():
    """Return a list of commands to register with the menu system"""
    return [
        {
            "name": "Apps",
            "description": "Launch applications",
            "callback": lambda: state_machine_ref.enter_mode(MenuMode.APP_LAUNCHER_MENU)
        }
    ]


def get_mode_handlers(state_machine):
    """Return mode handlers for this plugin"""
    # Store state machine reference for command callback
    global state_machine_ref
    state_machine_ref = state_machine

    return {
        MenuMode.APP_LAUNCHER_MENU: AppLauncherMenuHandler(state_machine)
    }
