"""
LED Feedback System

Provides visual feedback on the keyboard RGB LEDs:
- Mode-specific colors
- Value indicators (volume, gain)
- Animations (breathing, pulsing)
- Event feedback (press, rotate)
"""

import time
from typing import Optional, Tuple
from enum import Enum, auto


# Protocol constants (must match firmware)
HID_CMD_MARKER = 0xFE
CMD_LED_MODE = 0x10
CMD_LED_COLOR = 0x11


class LEDMode(Enum):
    """LED display modes"""
    SOLID = 0x00          # Solid color
    BREATHING = 0x01      # Breathing effect
    PULSE = 0x02          # Single pulse
    GRADIENT = 0x03       # Gradient across keys
    REACTIVE = 0x04       # React to keypresses


class LEDTheme:
    """Predefined LED color themes"""

    # Mode-specific colors
    NORMAL = (100, 100, 255)      # Blue - normal/command selection
    MEDIA = (255, 50, 255)        # Purple - media control
    VOLUME = (0, 255, 100)        # Cyan - volume control
    VOICEMEETER = (255, 150, 0)   # Orange - Voicemeeter
    WINDOW = (50, 255, 50)        # Green - window management
    ERROR = (255, 0, 0)           # Red - error
    SUCCESS = (0, 255, 0)         # Green - success

    # Event colors
    PRESS = (255, 255, 255)       # White - press event
    ROTATE_CW = (0, 150, 255)     # Light blue - clockwise
    ROTATE_CCW = (255, 100, 0)    # Orange - counter-clockwise


class LEDFeedback:
    """LED feedback controller"""

    def __init__(self, hid_device):
        """
        Args:
            hid_device: HID device handle for sending commands
        """
        self.device = hid_device
        self.current_color = LEDTheme.NORMAL
        self.enabled = True

    def set_mode_color(self, mode: str):
        """Set LED color based on menu mode

        Args:
            mode: Menu mode name (e.g., 'MEDIA', 'VOLUME', 'VOICEMEETER_MENU')
        """
        if not self.enabled:
            return

        # Map modes to colors
        color_map = {
            'NORMAL': LEDTheme.NORMAL,
            'MEDIA': LEDTheme.MEDIA,
            'VOLUME': LEDTheme.VOLUME,
            'VM_SYSTEM': LEDTheme.VOICEMEETER,
            'VM_MAIN_ROUTING': LEDTheme.VOICEMEETER,
            'VM_MUSIC_GAIN': LEDTheme.VOICEMEETER,
            'VM_MUSIC_ROUTING': LEDTheme.VOICEMEETER,
            'VM_COMM_GAIN': LEDTheme.VOICEMEETER,
            'VM_COMM_ROUTING': LEDTheme.VOICEMEETER,
            'VOICEMEETER_MENU': LEDTheme.VOICEMEETER,
            'WINDOW_MENU': LEDTheme.WINDOW,
            'WINDOW_CYCLE': LEDTheme.WINDOW,
            'WINDOW_SNAP': LEDTheme.WINDOW,
        }

        color = color_map.get(mode, LEDTheme.NORMAL)
        self.set_color(color)

    def set_color(self, rgb: Tuple[int, int, int]):
        """Set solid LED color

        Args:
            rgb: RGB tuple (0-255 each)
        """
        if not self.enabled or not self.device:
            return

        try:
            r, g, b = rgb
            self._send_command(CMD_LED_COLOR, r, g, b)
            self.current_color = rgb
        except Exception as e:
            print(f"[WARN] LED color command failed: {e}")

    def set_value_indicator(self, value: float, color_low: Tuple[int, int, int],
                           color_high: Tuple[int, int, int]):
        """Set LED color based on value (e.g., volume)

        Args:
            value: Value 0.0-1.0
            color_low: RGB at minimum value
            color_high: RGB at maximum value
        """
        if not self.enabled:
            return

        # Interpolate between colors
        r = int(color_low[0] + (color_high[0] - color_low[0]) * value)
        g = int(color_low[1] + (color_high[1] - color_low[1]) * value)
        b = int(color_low[2] + (color_high[2] - color_low[2]) * value)

        self.set_color((r, g, b))

    def pulse(self, color: Tuple[int, int, int] = None):
        """Trigger a pulse effect

        Args:
            color: Optional color (uses current if None)
        """
        if not self.enabled:
            return

        if color:
            self.set_color(color)

        # Send pulse mode command
        self._send_command(CMD_LED_MODE, LEDMode.PULSE.value, 0, 0)

    def breathing(self, color: Tuple[int, int, int] = None):
        """Start breathing effect

        Args:
            color: Optional color (uses current if None)
        """
        if not self.enabled:
            return

        if color:
            self.set_color(color)

        # Send breathing mode command
        self._send_command(CMD_LED_MODE, LEDMode.BREATHING.value, 0, 0)

    def flash_event(self, event_type: str):
        """Flash LED for event feedback

        Args:
            event_type: 'press', 'rotate_cw', 'rotate_ccw', 'success', 'error'
        """
        if not self.enabled:
            return

        color_map = {
            'press': LEDTheme.PRESS,
            'rotate_cw': LEDTheme.ROTATE_CW,
            'rotate_ccw': LEDTheme.ROTATE_CCW,
            'success': LEDTheme.SUCCESS,
            'error': LEDTheme.ERROR,
        }

        color = color_map.get(event_type, LEDTheme.PRESS)
        self.pulse(color)

    def _send_command(self, command: int, arg1: int, arg2: int, arg3: int):
        """Send LED command to firmware

        Args:
            command: Command byte
            arg1, arg2, arg3: Command arguments
        """
        if not self.device:
            return

        try:
            # Build packet
            packet = bytearray(32)
            packet[0] = HID_CMD_MARKER
            packet[1] = command
            packet[2] = arg1
            packet[3] = arg2
            packet[4] = arg3

            # Send to device
            self.device.write(bytes(packet))

        except Exception as e:
            print(f"[WARN] LED command failed: {e}")

    def enable(self):
        """Enable LED feedback"""
        self.enabled = True

    def disable(self):
        """Disable LED feedback"""
        self.enabled = False


# ============================================================================
# LED ANIMATOR
# ============================================================================

class LEDAnimator:
    """Animated LED effects"""

    def __init__(self, led_feedback: LEDFeedback):
        self.led = led_feedback
        self.running = False

    def volume_ramp(self, start_value: float, end_value: float, duration: float = 0.5):
        """Animate LED color as value changes

        Args:
            start_value: Starting value 0.0-1.0
            end_value: Ending value 0.0-1.0
            duration: Animation duration in seconds
        """
        import threading

        def animate():
            steps = int(duration * 60)  # 60 FPS
            for i in range(steps):
                if not self.running:
                    break

                t = i / steps
                value = start_value + (end_value - start_value) * t

                # Green to yellow to red gradient
                if value < 0.5:
                    color = (int(value * 2 * 255), 255, 0)
                else:
                    color = (255, int((1.0 - value) * 2 * 255), 0)

                self.led.set_color(color)
                time.sleep(duration / steps)

        self.running = True
        thread = threading.Thread(target=animate, daemon=True)
        thread.start()

    def stop(self):
        """Stop animation"""
        self.running = False


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("LED Feedback Test")
    print("Note: Requires connected keyboard with Raw HID firmware")

    # Mock HID device for testing
    class MockHIDDevice:
        def write(self, data):
            print(f"  LED Command: {' '.join(f'{b:02X}' for b in data[:8])}")

    mock_device = MockHIDDevice()
    led = LEDFeedback(mock_device)

    print("\nTesting mode colors:")
    for mode in ['NORMAL', 'MEDIA', 'VOLUME', 'VOICEMEETER_MENU', 'WINDOW_CYCLE']:
        print(f"  {mode}")
        led.set_mode_color(mode)
        time.sleep(0.5)

    print("\nTesting value indicator (volume 0-100%):")
    for vol in range(0, 101, 10):
        print(f"  Volume: {vol}%")
        led.set_value_indicator(vol/100, (0, 255, 0), (255, 0, 0))
        time.sleep(0.2)

    print("\nTesting event flashes:")
    for event in ['press', 'rotate_cw', 'rotate_ccw', 'success', 'error']:
        print(f"  Event: {event}")
        led.flash_event(event)
        time.sleep(0.5)

    print("\nDone!")
