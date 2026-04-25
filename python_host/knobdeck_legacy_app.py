"""
KnobDeck Legacy Host - Main Application
Legacy compatibility runtime for KnobDeck

Integrates:
- Raw HID communication (hid_test.py)
- State machine (menu_system.py)
- Mode handlers (mode_handlers.py)
- Windows APIs (windows_api.py)
- Overlay UI (overlay_ui.py)
"""

import sys
import time
import threading
import logging
import json
import os
import importlib
import pkgutil
from typing import Optional, List
from pathlib import Path
import subprocess

# Import our modules
from menu_system import MenuStateMachine, MenuMode
from mode_handlers import create_handlers
from windows_api import SystemAPI
from overlay_ui import UIManager
from voicemeeter_api import VoicemeeterController
from led_feedback import LEDFeedback
from tray_icon import TrayIcon

# Use Tkinter overlay (Qt has threading issues on Windows - requires main thread)
from overlay_enhanced import EnhancedUIManager
UI_BACKEND = "Tkinter"

# Qt overlay available but disabled - requires app restructuring to run on main thread
# from overlay_qt import EnhancedUIManager as QtEnhancedUIManager

# Import HID communication
import hid

# ============================================================================
# LOGGING SETUP
# ============================================================================

# Configure logging - handle both console and background execution
log_handlers = []

# Add file handler for pythonw.exe (no console) scenarios
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "knobdeck_legacy.log"
log_handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

# Add console handler if stdout is available (python.exe)
if sys.stdout is not None:
    try:
        log_handlers.append(logging.StreamHandler(sys.stdout))
    except:
        pass  # Ignore if console not available

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger("KnobDeck.Legacy")


# ============================================================================
# CONFIGURATION
# ============================================================================

DEFAULT_CONFIG = {
    "vendor_id": 0x3434,   # Keychron
    "product_id": 0x0311,  # V1 ANSI Encoder
    "usage_page": 0xFF60,
    "timeout_ms": 100,
    "reconnect_interval": 2.0,
    "max_reconnect_attempts": 30,
    "ui_theme": "DARK",
    "use_enhanced_ui": True,
    "led_feedback": True
}

def load_config():
    config_path = Path("config.json")
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                # Merge with defaults
                merged = DEFAULT_CONFIG.copy()
                merged.update(config)
                return merged
        except Exception as e:
            logger.error(f"Failed to load config.json: {e}")
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG

# Protocol constants (must match firmware)
HID_EVT_MARKER = 0xFD
EVT_ENCODER_CW = 0x01
EVT_ENCODER_CCW = 0x02
EVT_ENCODER_PRESS = 0x03
EVT_ENCODER_RELEASE = 0x04
EVT_ENCODER_LONG = 0x05
EVT_ENCODER_DOUBLE = 0x06


# ============================================================================
# PLUGIN SYSTEM
# ============================================================================

class PluginManager:
    def __init__(self, plugins_dir="plugins"):
        self.plugins_dir = plugins_dir
        self.plugins = []
        self.plugin_handlers = {}

    def load_plugins(self, state_machine):
        """Load plugins from plugins directory"""
        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir)
            return

        logger.info(f"Loading plugins from {self.plugins_dir}...")

        # Add plugins dir to path so we can import
        sys.path.append(os.path.abspath(self.plugins_dir))

        for _, name, _ in pkgutil.iter_modules([self.plugins_dir]):
            try:
                module = importlib.import_module(name)

                # Load commands
                if hasattr(module, 'get_commands'):
                    commands = module.get_commands()
                    for cmd in commands:
                        state_machine.commands.register(
                            cmd['name'],
                            cmd.get('description', ''),
                            cmd['callback']
                        )
                        logger.info(f"  + Registered plugin command: {cmd['name']}")

                # Load mode handlers
                if hasattr(module, 'get_mode_handlers'):
                    handlers = module.get_mode_handlers(state_machine)
                    self.plugin_handlers.update(handlers)
                    for mode_name in handlers.keys():
                        logger.info(f"  + Registered plugin mode handler: {mode_name}")

                self.plugins.append(module)
            except Exception as e:
                logger.error(f"Failed to load plugin {name}: {e}")

# ============================================================================
# COMMAND IMPLEMENTATIONS
# ============================================================================

def launch_playnite():
    """Launch Playnite in fullscreen mode"""
    try:
        subprocess.Popen(["playnite://playnite/fullscreen"], shell=True)
        logger.info("Launching Playnite fullscreen...")
    except Exception as e:
        logger.error(f"Failed to launch Playnite: {e}")


# ============================================================================
# KEYCHRON APPLICATION
# ============================================================================

class KeychronApp:
    """Main application - integrates HID, state machine, and UI"""

    def __init__(self, config):
        self.config = config
        
        # Components
        self.api = SystemAPI()
        self.vm = VoicemeeterController()
        self.state_machine = MenuStateMachine()
        self.plugin_manager = PluginManager()

        # UI - use enhanced or basic
        if config['use_enhanced_ui']:
            self.ui = EnhancedUIManager(theme=config['ui_theme'])
        else:
            self.ui = UIManager()

        # LED feedback (will be initialized after HID connection)
        self.led: Optional[LEDFeedback] = None
        self.led_enabled = config['led_feedback']

        # Tray icon
        self.tray_icon = TrayIcon(self)

        self.device: Optional[hid.device] = None
        self.running = threading.Event()
        self.is_pressed = False
        self.was_rotated_while_pressed = False
        self.ignore_next_release = False  # Prevents release after double-tap from triggering command

        # Threads
        self.hid_thread: Optional[threading.Thread] = None
        self.timeout_thread: Optional[threading.Thread] = None

        # Track command sequence for rotation direction
        self.last_command_index = 0

    def setup(self):
        """Initialize all components"""
        logger.info("Initializing KnobDeck legacy host...")

        # Check API status
        status = self.api.get_status()
        for name, available in status.items():
            level = logging.INFO if available else logging.WARNING
            logger.log(level, f"API {name}: {'Available' if available else 'Unavailable'}")

        if not self.api.is_available():
            logger.error("No Windows APIs available! Install requirements.")
            return False

        # Try to connect to Voicemeeter
        logger.info("Connecting to Voicemeeter...")
        if self.vm.connect():
            logger.info("Voicemeeter Potato connected")
        else:
            logger.warning("Voicemeeter not available - audio routing disabled")

        # Register commands
        self._register_commands()

        # Load Plugins
        self.plugin_manager.load_plugins(self.state_machine)

        # Register mode handlers (built-in)
        handlers = create_handlers(self.api, self.state_machine, self.vm)
        for mode, handler in handlers.items():
            self.state_machine.register_mode_handler(mode, handler)

        # Register plugin mode handlers
        for mode, handler in self.plugin_manager.plugin_handlers.items():
            self.state_machine.register_mode_handler(mode, handler)

        # Store references in state machine for handlers
        self.state_machine.api = self.api
        self.state_machine.vm = self.vm

        # Set callbacks
        self.state_machine.set_ui_callback(self._on_ui_update)
        self.state_machine.set_notification_callback(self._on_notification)
        self.state_machine.set_ui_hide_callback(self._on_ui_hide)

        # Start UI
        logger.info(f"Starting overlay UI ({UI_BACKEND} backend)...")
        self.ui.start()

        # Start tray icon
        logger.info("Starting system tray icon...")
        self.tray_icon.start()

        return True

    def _register_commands(self):
        """Register built-in commands"""
        # Always register System Volume Control
        self.state_machine.commands.register(
            "Volume Control",
            "Adjust system volume and mute",
            self._enter_volume_mode
        )

        # Register Voicemeeter if available
        if self.vm.is_available():
            self.state_machine.commands.register(
                "Voicemeeter Control",
                "Audio routing and gain control",
                self._enter_voicemeeter_menu
            )

        self.state_machine.commands.register(
            "Media Controls",
            "Play/pause, next/prev track",
            self._enter_media_mode
        )

        self.state_machine.commands.register(
            "Theme Selector",
            "Change UI color theme",
            self._enter_theme_menu
        )
        
        self.state_machine.commands.register(
            "Window Manager",
            "Cycle and snap windows",
            self._enter_window_menu_mode
        )
        self.state_machine.commands.register(
            "Launch Playnite",
            "Open Playnite fullscreen",
            launch_playnite
        )

    def _enter_theme_menu(self):
        """Enter theme selection mode"""
        self.state_machine.enter_mode(MenuMode.THEME_MENU)

    def _enter_voicemeeter_menu(self):
        """Enter Voicemeeter menu mode"""
        self.state_machine.enter_mode(MenuMode.VOICEMEETER_MENU)

    def _enter_volume_mode(self):
        """Enter volume control mode (fallback when Voicemeeter unavailable)"""
        # Use system volume control mode
        self.state_machine.enter_mode(MenuMode.VOLUME)

    def _enter_media_mode(self):
        """Enter media control mode"""
        self.state_machine.enter_mode(MenuMode.MEDIA)

    def _enter_window_menu_mode(self):
        """Enter window manager menu"""
        self.state_machine.enter_mode(MenuMode.WINDOW_MENU)

    def save_config(self):
        """Save current configuration to config.json"""
        config_path = Path("config.json")
        try:
            with open(config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def _on_ui_update(self, display: dict):
        """Callback: Update UI overlay"""
        # Extract special control keys
        icons = display.pop('icons', None)
        progress = display.pop('progress', None)
        theme_name = display.pop('set_theme', None)
        preview_theme = display.pop('preview_theme', None)
        theme_colors = display.pop('set_theme_color', None)

        # Apply theme change (SAVE)
        if theme_name and hasattr(self.ui, 'set_theme'):
            self.ui.set_theme(theme_name)
            # Save to config
            self.config['ui_theme'] = theme_name
            self.save_config()

        # Apply theme preview (NO SAVE)
        if preview_theme and hasattr(self.ui, 'set_theme'):
            self.ui.set_theme(preview_theme)
            
        # Apply specific color updates
        if theme_colors and hasattr(self.ui, 'update_theme_color'):
            self.ui.update_theme_color(theme_colors)

        # Persistence: save theme if requested
        save_request = display.pop('save_theme', None)
        if save_request and hasattr(self.ui, 'save_theme'):
            self.ui.save_theme(save_request)

        # Show menu with enhanced data
        if hasattr(self.ui, 'show_menu'):
            if icons or progress is not None:
                # Enhanced UI supports icons and progress
                self.ui.show_menu(display, progress=progress, icons=icons)
            else:
                self.ui.show_menu(display)

    def _on_notification(self, message: str, duration: int):
        """Callback: Show notification"""
        self.ui.show_notification(message, duration)

    def _on_ui_hide(self):
        """Callback: Hide UI overlay"""
        if hasattr(self.ui, 'hide_menu'):
            self.ui.hide_menu()

    def connect_hid(self) -> bool:
        """Connect to keyboard HID device with retries"""
        logger.info("Searching for keyboard...")
        
        vid = self.config['vendor_id']
        pid = self.config['product_id']
        usage_page = self.config['usage_page']
        
        attempts = 0
        max_attempts = self.config['max_reconnect_attempts']
        
        while attempts < max_attempts and self.running.is_set():
            try:
                # Find Raw HID interface
                devices = hid.enumerate(vid, pid)
                raw_hid_path = None

                for dev in devices:
                    if dev['usage_page'] == usage_page:
                        raw_hid_path = dev['path']
                        break

                if raw_hid_path:
                    self.device = hid.device()
                    self.device.open_path(raw_hid_path)
                    self.device.set_nonblocking(0)  # Blocking reads

                    manufacturer = self.device.get_manufacturer_string()
                    product = self.device.get_product_string()
                    logger.info(f"Connected to: {manufacturer} {product} (VID: 0x{vid:04X}, PID: 0x{pid:04X})")

                    # Initialize LED feedback
                    if self.led_enabled:
                        self.led = LEDFeedback(self.device)
                        self.led.set_mode_color('NORMAL')
                        self.state_machine.led = self.led
                        logger.info("LED feedback enabled")

                    return True
                
                attempts += 1
                if attempts % 5 == 0:
                    logger.info(f"Waiting for device... (Attempt {attempts}/{max_attempts})")
                time.sleep(self.config['reconnect_interval'])

            except Exception as e:
                logger.debug(f"Connection attempt failed: {e}")
                time.sleep(self.config['reconnect_interval'])

        logger.error("Could not find configured keyboard HID device.")
        return False

    def hid_reader_loop(self):
        """HID reader thread - process encoder events"""
        logger.info("HID Reader thread started")

        while self.running.is_set():
            try:
                # Blocking read with timeout
                data = self.device.read(32, timeout_ms=self.config['timeout_ms'])
                if not data or len(data) == 0:
                    continue

                # Parse event
                if data[0] == HID_EVT_MARKER:
                    event_type = data[1]
                    encoder_id = data[2]
                    value = data[3]

                    # Route to state machine
                    self._handle_encoder_event(event_type, value)

            except Exception as e:
                if self.running.is_set():
                    logger.error(f"HID read error: {e}")
                    # Simple reconnection logic could go here
                break

        logger.info("HID Reader thread stopped")

    def _handle_encoder_event(self, event_type: int, value: int):
        """Route encoder events to state machine"""

        # Debug logging
        # logger.info(f"Event: {event_type}, Pressed: {self.is_pressed}")

        # Get dynamic item count from state machine's command registry
        num_items = self.state_machine.commands.count() if hasattr(self.state_machine, 'commands') else 4

        if event_type == EVT_ENCODER_CW:
            # Quick volume control: Press + Rotate = Instant volume adjustment
            if self.is_pressed:
                self.was_rotated_while_pressed = True

                # Hide any open menu UI (from previous browsing)
                if self.state_machine.state.menu_mode == MenuMode.NORMAL:
                    self._on_ui_hide()

                self.api.volume.adjust_volume(2)
                vol = self.api.volume.get_volume()
                self.ui.show_notification(f"Volume: {vol}%", 500)
                if self.led: self.led.flash_event('rotate_cw')
                return

            # Clockwise rotation (Normal)
            next_index = (self.last_command_index + 1) % num_items
            self.state_machine.handle_rotation(next_index)
            self.last_command_index = next_index
            if self.led: self.led.flash_event('rotate_cw')

        elif event_type == EVT_ENCODER_CCW:
            # Quick volume control: Press + Rotate = Instant volume adjustment
            if self.is_pressed:
                self.was_rotated_while_pressed = True

                # Hide any open menu UI (from previous browsing)
                if self.state_machine.state.menu_mode == MenuMode.NORMAL:
                    self._on_ui_hide()

                self.api.volume.adjust_volume(-2)
                vol = self.api.volume.get_volume()
                self.ui.show_notification(f"Volume: {vol}%", 500)
                if self.led: self.led.flash_event('rotate_ccw')
                return

            # Counter-clockwise rotation (Normal)
            next_index = (self.last_command_index - 1) % num_items
            self.state_machine.handle_rotation(next_index)
            self.last_command_index = next_index
            if self.led: self.led.flash_event('rotate_ccw')

        elif event_type == EVT_ENCODER_PRESS:
            self.is_pressed = True
            self.was_rotated_while_pressed = False
            if self.led: self.led.flash_event('press')

        elif event_type == EVT_ENCODER_RELEASE:
            self.is_pressed = False
            # Skip if this release follows a double-tap (which already exited the menu)
            if self.ignore_next_release:
                self.ignore_next_release = False
                return
            # If we were doing quick volume adjustment, hide the notification immediately
            if self.was_rotated_while_pressed and self.state_machine.state.menu_mode == MenuMode.NORMAL:
                self._on_ui_hide()
            # Only execute click if we didn't use the press for rotation
            elif not self.was_rotated_while_pressed:
                self.state_machine.handle_press()

        elif event_type == EVT_ENCODER_LONG:
            self.is_pressed = False
            self.was_rotated_while_pressed = False
            self.state_machine.handle_long_press()

        elif event_type == EVT_ENCODER_DOUBLE:
            self.is_pressed = False
            self.was_rotated_while_pressed = False
            self.ignore_next_release = True  # Prevent subsequent release from executing command
            # Ensure we reset click count in state machine to avoid conflict
            self.state_machine.state.click_count = 0
            self.state_machine.handle_double_tap()

    def timeout_check_loop(self):
        """Check for menu timeout in background"""
        while self.running.is_set():
            time.sleep(0.5)
            if self.state_machine.check_menu_timeout():
                self.state_machine.exit_menu_mode()

    def run(self):
        """Main run loop"""
        if not self.setup():
            return False

        # Flag that we are starting
        self.running.set()

        # Connect with retry
        if not self.connect_hid():
            self.stop()
            return False

        # Start HID reader thread
        self.hid_thread = threading.Thread(target=self.hid_reader_loop, daemon=True)
        self.hid_thread.start()

        # Start timeout checker thread
        self.timeout_thread = threading.Thread(target=self.timeout_check_loop, daemon=True)
        self.timeout_thread.start()

        # Show startup notification
        msg = "KnobDeck + Voicemeeter Active" if self.vm.is_available() else "KnobDeck Active"
        self.ui.show_notification(msg, 2000)

        logger.info("System ready! Rotate or press encoder to interact.")
        logger.info("Press Ctrl+C to exit.")

        # Main loop - just keep alive
        try:
            while self.running.is_set():
                time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info("Shutting down request received...")
            self.stop()

        return True

    def stop(self):
        """Stop application"""
        self.running.clear()

        # Stop tray icon
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.stop()

        # Close HID device
        if self.device:
            try:
                self.device.close()
            except:
                pass

        # Disconnect from Voicemeeter
        if hasattr(self, 'vm') and self.vm:
            self.vm.disconnect()

        # Stop UI
        if hasattr(self, 'ui') and self.ui:
            self.ui.quit()

        logger.info("Goodbye!")


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    import argparse
    
    config = load_config()

    parser = argparse.ArgumentParser(description='KnobDeck Legacy Host')
    # Load available themes from themes.json
    available_themes = ['DARK', 'LIGHT', 'CYBER']  # defaults
    themes_path = Path(__file__).parent / 'themes.json'
    if themes_path.exists():
        try:
            with open(themes_path, 'r') as f:
                available_themes = list(json.load(f).keys())
        except:
            pass

    parser.add_argument('--theme', choices=available_themes, default=None,
                       help=f'UI theme. Available: {", ".join(available_themes)}')
    parser.add_argument('--classic-ui', action='store_true',
                       help='Use basic UI instead of enhanced')
    parser.add_argument('--test-ui', action='store_true',
                       help='Test UI without connecting to keyboard')

    args = parser.parse_args()

    # Override config with args only if explicitly provided
    if args.theme is not None:
        config['ui_theme'] = args.theme
    # Ensure ui_theme has a valid value
    if config.get('ui_theme') not in available_themes:
        config['ui_theme'] = 'DARK'
    if args.classic_ui:
        config['use_enhanced_ui'] = False

    if args.test_ui:
        run_ui_test(config)
        return

    # Normal mode
    app = KeychronApp(config)
    success = app.run()
    sys.exit(0 if success else 1)

def run_ui_test(config):
    """Run UI test mode"""
    logger.info("UI Test Mode")
    from overlay_enhanced import EnhancedUIManager
    import time

    ui = EnhancedUIManager(theme=config['ui_theme'])
    ui.start()

    # Demo different menu modes
    demos = [
        {
            'display': {'left': 'Prev', 'center': 'Pause', 'right': 'Next', 'title': '♪ Media'},
            'icons': {'left': '⏮', 'center': '⏯', 'right': '⏭'},
            'name': 'Media Control'
        },
        {
            'display': {'left': '-', 'center': '50%', 'right': '+', 'title': '🔊 Volume'},
            'progress': 0.5,
            'icons': {'left': '−', 'center': '🔊', 'right': '+'},
            'name': 'Volume Control'
        }
    ]

    for demo in demos:
        logger.info(f"Testing: {demo['name']}")
        ui.show_notification(demo['name'], 1500)
        time.sleep(2)
        ui.show_menu(demo['display'], progress=demo.get('progress'), icons=demo.get('icons'))
        time.sleep(3)

    ui.hide_menu()
    time.sleep(1)
    ui.quit()

if __name__ == "__main__":
    main()

