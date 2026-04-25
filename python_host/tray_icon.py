"""
System Tray Icon for KnobDeck
"""

import sys
import logging
import threading
import subprocess
from pathlib import Path

try:
    from PIL import Image, ImageDraw
    import pystray
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False
    logging.warning("pystray or PIL not installed. Tray icon will not be available.")
    logging.warning("Install with: pip install pystray Pillow")

logger = logging.getLogger("KnobDeck.TrayIcon")


class TrayIcon:
    """System tray icon manager"""

    def __init__(self, app_instance):
        self.app = app_instance
        self.icon = None
        self.running = False

        if not PYSTRAY_AVAILABLE:
            logger.warning("Tray icon unavailable - missing dependencies")
            return

    def create_icon_image(self):
        """Create a KnobDeck tray icon image."""
        asset_path = Path(__file__).parent / "assets" / "knobdeck_tray.png"
        if asset_path.exists():
            try:
                return Image.open(asset_path)
            except Exception:
                pass

        width = 64
        height = 64

        image = Image.new('RGB', (width, height), color='#0E1A2A')
        draw = ImageDraw.Draw(image)

        # Dial ring
        draw.ellipse([6, 6, 58, 58], outline='#2FB8FF', width=4)
        draw.ellipse([19, 19, 45, 45], fill='#29D3A4')
        # Cross marks
        draw.line([32, 10, 32, 18], fill='#2FB8FF', width=3)
        draw.line([32, 46, 32, 54], fill='#2FB8FF', width=3)
        draw.line([10, 32, 18, 32], fill='#2FB8FF', width=3)
        draw.line([46, 32, 54, 32], fill='#2FB8FF', width=3)
        # Small base strip hinting keyboard deck
        draw.rounded_rectangle([14, 50, 50, 60], radius=4, fill='#1D3550', outline='#2FB8FF', width=1)

        return image

    def on_quit(self, icon, item):
        """Handle quit action"""
        logger.info("Quit requested from tray icon")
        self.running = False
        
        # Explicitly hide icon to prevent ghosting
        icon.visible = False
        icon.stop()
        
        # Small sleep to allow Windows to process the icon removal
        import time
        time.sleep(0.2)

        # Stop the application
        if hasattr(self.app, 'quit'):
            self.app.quit()
        elif hasattr(self.app, 'stop'):
            self.app.stop()

        # Force exit if needed - this should ideally not be necessary if app.quit() works
        # sys.exit(0) # Removed to allow graceful shutdown
    def on_show_status(self, icon, item):
        """Show current status"""
        logger.info("Status requested from tray icon")

        # Get status info
        mode = "Idle"
        if hasattr(self.app, 'state_machine'):
            current_mode = getattr(getattr(self.app.state_machine, 'state', None), 'menu_mode', None)
            if current_mode:
                mode = str(current_mode).split('.')[-1]

        vm_status = "Not connected"
        if hasattr(self.app, 'vm') and self.app.vm.is_available():
            vm_status = "Connected"

        logger.info(f"Status - Mode: {mode}, Voicemeeter: {vm_status}")

    def _settings(self):
        if hasattr(self.app, 'get_runtime_settings'):
            return self.app.get_runtime_settings()
        return {}

    def _checked(self, key, expected):
        return lambda item: self._settings().get(key) == expected

    def _checked_theme(self, theme_name):
        return lambda item: getattr(self.app, 'config', {}).get('ui_theme') == theme_name

    def _update_menu(self):
        if self.icon:
            try:
                self.icon.update_menu()
            except Exception:
                pass

    def on_set_setting(self, icon, item, key, value):
        """Set an app runtime setting and persist it."""
        if hasattr(self.app, 'update_setting'):
            self.app.update_setting(key, value)
            logger.info(f"Updated setting: {key}={value}")
            self._update_menu()

    def _setting_action(self, key, value):
        def _handler(icon, item):
            self.on_set_setting(icon, item, key, value)
        return _handler

    def on_set_theme(self, icon, item, theme_name):
        """Apply and persist theme."""
        if hasattr(self.app, 'set_theme'):
            self.app.set_theme(theme_name)
            logger.info(f"Updated theme: {theme_name}")
            self._update_menu()

    def _theme_action(self, theme_name):
        def _handler(icon, item):
            self.on_set_theme(icon, item, theme_name)
        return _handler

    def on_open_config(self, icon, item):
        """Open config.json in default editor."""
        config_path = Path(__file__).parent / 'config.json'
        try:
            subprocess.Popen(['notepad.exe', str(config_path)])
        except Exception as e:
            logger.error(f"Failed to open config: {e}")

    def on_open_settings(self, icon, item):
        """Open GUI settings window."""
        try:
            if hasattr(self.app, 'open_settings_window'):
                self.app.open_settings_window()
        except Exception as e:
            logger.error(f"Failed to open settings window: {e}")

    def on_restart(self, icon, item):
        """Restart the app process."""
        logger.info("Restart requested from tray icon")
        script_path = Path(__file__).parent / 'knobdeck_app.py'
        try:
            subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=str(script_path.parent),
                close_fds=True
            )
            self.on_quit(icon, item)
        except Exception as e:
            logger.error(f"Failed to restart app: {e}")

    def on_open_tutorial(self, icon, item):
        """Open onboarding/tutorial dialog."""
        try:
            if hasattr(self.app, 'open_onboarding_tutorial'):
                self.app.open_onboarding_tutorial()
        except Exception as e:
            logger.error(f"Failed to open tutorial: {e}")

    def create_menu(self):
        """Create the tray icon menu"""
        available_themes = ['DARK', 'LIGHT', 'CYBER']
        if hasattr(self.app, 'get_available_themes'):
            available_themes = self.app.get_available_themes()

        settings_menu = pystray.Menu(
            pystray.MenuItem(
                "Notifications",
                lambda icon, item: self.on_set_setting(
                    icon,
                    item,
                    'notifications_enabled',
                    not self._settings().get('notifications_enabled', True)
                ),
                checked=lambda item: bool(self._settings().get('notifications_enabled', True))
            ),
            pystray.MenuItem(
                "Submenu Auto-Timeout",
                lambda icon, item: self.on_set_setting(
                    icon,
                    item,
                    'submenu_timeout_enabled',
                    not self._settings().get('submenu_timeout_enabled', True)
                ),
                checked=lambda item: bool(self._settings().get('submenu_timeout_enabled', True))
            ),
            pystray.MenuItem(
                "Restore Voicemeeter On Start",
                lambda icon, item: self.on_set_setting(
                    icon,
                    item,
                    'restore_voicemeeter_on_start',
                    not self._settings().get('restore_voicemeeter_on_start', False)
                ),
                checked=lambda item: bool(self._settings().get('restore_voicemeeter_on_start', False))
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Menu Timeout",
                pystray.Menu(
                    pystray.MenuItem("1.0s", self._setting_action('menu_timeout_ms', 1000), checked=self._checked('menu_timeout_ms', 1000)),
                    pystray.MenuItem("1.5s", self._setting_action('menu_timeout_ms', 1500), checked=self._checked('menu_timeout_ms', 1500)),
                    pystray.MenuItem("2.5s", self._setting_action('menu_timeout_ms', 2500), checked=self._checked('menu_timeout_ms', 2500)),
                    pystray.MenuItem("3.0s", self._setting_action('menu_timeout_ms', 3000), checked=self._checked('menu_timeout_ms', 3000)),
                    pystray.MenuItem("4.0s", self._setting_action('menu_timeout_ms', 4000), checked=self._checked('menu_timeout_ms', 4000)),
                )
            ),
            pystray.MenuItem(
                "Double Click Window",
                pystray.Menu(
                    pystray.MenuItem("250ms", self._setting_action('double_click_ms', 250), checked=self._checked('double_click_ms', 250)),
                    pystray.MenuItem("300ms", self._setting_action('double_click_ms', 300), checked=self._checked('double_click_ms', 300)),
                    pystray.MenuItem("400ms", self._setting_action('double_click_ms', 400), checked=self._checked('double_click_ms', 400)),
                )
            ),
            pystray.MenuItem(
                "Volume Step",
                pystray.Menu(
                    pystray.MenuItem("1", self._setting_action('volume_step', 1), checked=self._checked('volume_step', 1)),
                    pystray.MenuItem("2", self._setting_action('volume_step', 2), checked=self._checked('volume_step', 2)),
                    pystray.MenuItem("5", self._setting_action('volume_step', 5), checked=self._checked('volume_step', 5)),
                )
            ),
            pystray.MenuItem(
                "Quick Volume Auto-Hide",
                pystray.Menu(
                    pystray.MenuItem("600ms", self._setting_action('quick_volume_hide_ms', 600), checked=self._checked('quick_volume_hide_ms', 600)),
                    pystray.MenuItem("800ms", self._setting_action('quick_volume_hide_ms', 800), checked=self._checked('quick_volume_hide_ms', 800)),
                    pystray.MenuItem("1200ms", self._setting_action('quick_volume_hide_ms', 1200), checked=self._checked('quick_volume_hide_ms', 1200)),
                )
            ),
            pystray.MenuItem(
                "Theme",
                pystray.Menu(*[
                    pystray.MenuItem(theme_name, self._theme_action(theme_name), checked=self._checked_theme(theme_name))
                    for theme_name in available_themes
                ])
            ),
        )

        return pystray.Menu(
            pystray.MenuItem("KnobDeck", lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Show Status", self.on_show_status),
            pystray.MenuItem("Open Settings", self.on_open_settings),
            pystray.MenuItem("Open Tutorial", self.on_open_tutorial),
            pystray.MenuItem("Settings", settings_menu),
            pystray.MenuItem("Open Config", self.on_open_config),
            pystray.MenuItem("Restart App", self.on_restart),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.on_quit)
        )

    def setup(self, icon):
        """Setup callback - makes icon visible"""
        icon.visible = True
        logger.info("Tray icon is now visible")

    def run(self):
        """Run the tray icon (blocking)"""
        if not PYSTRAY_AVAILABLE:
            logger.warning("Cannot start tray icon - dependencies not available")
            return

        try:
            self.running = True

            # Create icon image
            image = self.create_icon_image()

            # Create icon with setup callback
            self.icon = pystray.Icon(
                "knobdeck",
                image,
                "KnobDeck",
                menu=self.create_menu()
            )

            logger.info("Starting tray icon with setup callback...")

            # Run with setup callback - this is REQUIRED on Windows
            self.icon.run(setup=self.setup)
            logger.info("Tray icon stopped")
        except Exception as e:
            logger.error(f"Failed to start tray icon: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def start(self):
        """Start the tray icon in a background thread"""
        if not PYSTRAY_AVAILABLE:
            logger.warning("Tray icon not available")
            return

        # Use a non-daemon thread so it stays alive
        thread = threading.Thread(target=self.run, daemon=False)
        thread.start()
        logger.info("Tray icon thread started")

    def stop(self):
        """Stop the tray icon"""
        if self.icon:
            self.icon.visible = False
            self.icon.stop()
            self.running = False
            logger.info("Tray icon stopped")
