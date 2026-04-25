"""
HID Reader Thread - QThread implementation for reading keyboard events

Runs HID communication in a background thread while Qt UI runs on main thread.
"""

from PyQt6.QtCore import QThread, pyqtSignal
import hid
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Custom firmware protocol constants
HID_CMD_MARKER = 0xFE
CMD_SET_MODE = 0x10
CMD_HEARTBEAT = 0x12
MODE_DEFAULT = 0x00

class HIDReaderThread(QThread):
    """Background thread for reading HID events from keyboard"""

    # Signals for HID events
    event_received = pyqtSignal(int, int, int)  # event_type, encoder_id, value
    connection_lost = pyqtSignal()
    connection_established = pyqtSignal()
    error_occurred = pyqtSignal(str)

    # HID Event types
    EVENT_CW = 0x01          # Clockwise rotation
    EVENT_CCW = 0x02         # Counter-clockwise rotation
    EVENT_PRESS = 0x03       # Button press
    EVENT_RELEASE = 0x04     # Button release
    EVENT_LONG_PRESS = 0x05  # Long press
    EVENT_DOUBLE_CLICK = 0x06 # Double click

    def __init__(self, vendor_id: int, product_id: int, usage_page: int, usage: int):
        super().__init__()

        self.vendor_id = vendor_id
        self.product_id = product_id
        self.usage_page = usage_page
        self.usage = usage

        self.device: Optional[hid.device] = None
        self.running = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._heartbeat_interval = 0.75
        self._last_heartbeat = 0.0

    def run(self):
        """Main thread loop - sends heartbeats to keep firmware link active.
        Events are delivered via F13-F18 keyboard shortcuts instead
        of raw HID reads, so VIA gets uncontested access to the HID endpoint.
        """
        self.running = True

        while self.running:
            try:
                # Try to connect if not connected
                if not self.device:
                    if not self._connect():
                        time.sleep(2)  # Wait before retry
                        continue

                self._send_heartbeat_if_needed()
                time.sleep(0.1)  # 100 ms sleep — no read needed

            except Exception as e:
                logger.error(f"HID heartbeat error: {e}")
                self._handle_connection_error()
                time.sleep(1)

        # Cleanup
        self._disconnect()

    def stop(self):
        """Stop the thread"""
        self.running = False

    def _connect(self) -> bool:
        """Connect to HID device"""
        try:
            logger.info(f"Connecting to HID device (VID: 0x{self.vendor_id:04X}, PID: 0x{self.product_id:04X})")

            # Find device
            devices = hid.enumerate(self.vendor_id, self.product_id)
            target_device = None

            for dev in devices:
                if dev['usage_page'] == self.usage_page and dev['usage'] == self.usage:
                    target_device = dev
                    break

            if not target_device:
                if self._reconnect_attempts == 0:  # Only log once
                    logger.warning("HID device not found")
                self._reconnect_attempts += 1
                return False

            # Open device
            self.device = hid.device()
            self.device.open_path(target_device['path'])
            self.device.set_nonblocking(False)
            self._initialize_protocol()
            self._last_heartbeat = time.monotonic()

            logger.info("HID device connected successfully")
            self.connection_established.emit()
            self._reconnect_attempts = 0
            return True

        except Exception as e:
            logger.error(f"HID connection error: {e}")
            self.device = None
            self._reconnect_attempts += 1
            return False

    def _initialize_protocol(self):
        """Arm the firmware wheel protocol after connection."""
        if not self.device:
            return

        try:
            self._send_command(CMD_SET_MODE, MODE_DEFAULT)
            self._send_command(CMD_HEARTBEAT)
        except Exception as e:
            logger.warning(f"Failed to initialize HID protocol handshake: {e}")

    def _send_command(self, command: int, *args: int):
        """Send a host command packet to the firmware."""
        packet = bytearray(32)
        packet[0] = HID_CMD_MARKER
        packet[1] = command
        for index, value in enumerate(args[:29], start=2):
            packet[index] = value & 0xFF
        self._write_compat(bytes(packet))

    def _send_heartbeat_if_needed(self):
        """Keep the firmware wheel protocol armed while the app is attached."""
        if not self.device:
            return

        now = time.monotonic()
        if (now - self._last_heartbeat) >= self._heartbeat_interval:
            self._send_command(CMD_HEARTBEAT)
            self._last_heartbeat = now

    def _write_compat(self, payload: bytes):
        """Write HID packet while tolerating driver report-ID differences."""
        if not self.device:
            return
        try:
            self.device.write(payload)
            return
        except Exception:
            pass
        # Some HID stacks expect a report-id prefix (0x00).
        self.device.write(bytes([0x00]) + payload)

    def _disconnect(self):
        """Disconnect from HID device"""
        if self.device:
            try:
                self.device.close()
                logger.info("HID device disconnected")
            except:
                pass
            self.device = None

    def _handle_connection_error(self):
        """Handle connection loss"""
        logger.warning("HID connection lost")
        self._disconnect()
        self.connection_lost.emit()

    def _process_hid_data(self, data: bytes):
        """Process incoming HID data packet"""
        if len(data) < 4:
            return

        # Check for event marker
        if data[0] != 0xFD:
            return

        event_type = data[1]
        encoder_id = data[2]
        value = data[3]

        # Emit signal with event data
        self.event_received.emit(event_type, encoder_id, value)

    def send_hid_data(self, data: bytes):
        """Send data to HID device (called from main thread via queued connection)"""
        if self.device:
            try:
                self._write_compat(data)
            except Exception as e:
                logger.error(f"HID write error: {e}")


if __name__ == "__main__":
    """Test HID reader thread"""
    import sys
    from PyQt6.QtWidgets import QApplication

    logging.basicConfig(level=logging.INFO)

    app = QApplication(sys.argv)

    # Test connection
    reader = HIDReaderThread(
        vendor_id=0x3434,
        product_id=0x0311,
        usage_page=0xFF60,
        usage=0x61
    )

    def on_event(event_type, encoder_id, value):
        print(f"Event: type={event_type}, encoder={encoder_id}, value={value}")

    def on_connected():
        print("Connected!")

    def on_disconnected():
        print("Disconnected!")

    reader.event_received.connect(on_event)
    reader.connection_established.connect(on_connected)
    reader.connection_lost.connect(on_disconnected)

    reader.start()

    print("HID Reader thread running. Press Ctrl+C to exit.")

    try:
        sys.exit(app.exec())
    finally:
        reader.stop()
        reader.wait()
