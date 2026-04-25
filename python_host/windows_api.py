"""
Windows API Integration Module

Provides system control functionality:
- Volume control (using pycaw)
- Media keys (using keyboard simulation)
- Window management (using pywin32)

Requirements:
    pip install pycaw comtypes pywin32
"""

import sys
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass


# ============================================================================
# VOLUME CONTROL (using pycaw)
# ============================================================================

class VolumeControl:
    """Windows volume control using Core Audio API"""

    def __init__(self):
        self.available = False
        self.interface = None

        try:
            from pycaw.pycaw import AudioUtilities

            # Get default audio endpoint
            devices = AudioUtilities.GetSpeakers()
            # Use EndpointVolume property directly
            self.interface = devices.EndpointVolume
            self.available = True

        except Exception as e:
            print(f"[WARN] Volume control not available: {e}")
            self.available = False

    def _get_audio_utilities(self):
        try:
            from pycaw.pycaw import AudioUtilities
            return AudioUtilities
        except Exception:
            return None

    def get_volume(self) -> int:
        """Get current volume (0-100)"""
        if not self.available:
            return 0
        try:
            volume = self.interface.GetMasterVolumeLevelScalar()
            return int(volume * 100)
        except:
            return 0

    def set_volume(self, percent: int):
        """Set volume (0-100)"""
        if not self.available:
            return
        try:
            percent = max(0, min(100, percent))
            self.interface.SetMasterVolumeLevelScalar(percent / 100, None)
        except:
            pass

    def adjust_volume(self, delta: int):
        """Adjust volume by delta"""
        current = self.get_volume()
        self.set_volume(current + delta)

    def get_mute(self) -> bool:
        """Get mute state"""
        if not self.available:
            return False
        try:
            return bool(self.interface.GetMute())
        except:
            return False

    def set_mute(self, muted: bool):
        """Set mute state"""
        if not self.available:
            return
        try:
            self.interface.SetMute(1 if muted else 0, None)
        except:
            pass

    def toggle_mute(self):
        """Toggle mute"""
        self.set_mute(not self.get_mute())

    def get_app_sessions(self) -> List[Dict[str, Any]]:
        """Return active per-app audio sessions."""
        util = self._get_audio_utilities()
        if util is None:
            return []
        sessions = []
        try:
            for s in util.GetAllSessions():
                if not s or not s.SimpleAudioVolume:
                    continue
                process = getattr(s, "Process", None)
                name = ""
                pid = 0
                if process is not None:
                    try:
                        name = str(process.name() or "")
                        pid = int(process.pid or 0)
                    except Exception:
                        pass
                if not name:
                    # Skip anonymous/system session noise for mixer UX.
                    continue
                vol = 0
                muted = False
                try:
                    vol = int(float(s.SimpleAudioVolume.GetMasterVolume()) * 100.0)
                except Exception:
                    pass
                try:
                    muted = bool(s.SimpleAudioVolume.GetMute())
                except Exception:
                    pass
                sessions.append({
                    "id": f"{name.lower()}:{pid}",
                    "name": name,
                    "pid": pid,
                    "volume": max(0, min(100, vol)),
                    "muted": muted,
                    "session": s,
                })
        except Exception:
            return []
        sessions.sort(key=lambda x: (x["name"].lower(), x["pid"]))
        return sessions

    def set_app_volume(self, session_obj: Any, percent: int) -> bool:
        if not session_obj:
            return False
        try:
            p = max(0, min(100, int(percent)))
            session_obj.SimpleAudioVolume.SetMasterVolume(p / 100.0, None)
            return True
        except Exception:
            return False

    def adjust_app_volume(self, session_obj: Any, delta: int) -> bool:
        if not session_obj:
            return False
        try:
            current = int(float(session_obj.SimpleAudioVolume.GetMasterVolume()) * 100.0)
            return self.set_app_volume(session_obj, current + int(delta))
        except Exception:
            return False

    def toggle_app_mute(self, session_obj: Any) -> bool:
        if not session_obj:
            return False
        try:
            muted = bool(session_obj.SimpleAudioVolume.GetMute())
            session_obj.SimpleAudioVolume.SetMute(0 if muted else 1, None)
            return True
        except Exception:
            return False


# ============================================================================
# MEDIA KEYS (using SendInput for media key simulation)
# ============================================================================

class MediaControl:
    """Windows media key control"""

    def __init__(self):
        self.available = False
        try:
            import win32api
            import win32con
            self.win32api = win32api
            self.win32con = win32con
            self.available = True
        except ImportError:
            print("[WARN] Media control not available (install pywin32)")
            self.available = False

    def _send_key(self, vk_code):
        """Send a virtual key press with scan code"""
        if not self.available:
            return
        try:
            # Get scan code for better compatibility
            scan_code = self.win32api.MapVirtualKey(vk_code, 0)
            
            # Press
            self.win32api.keybd_event(vk_code, scan_code, 0, 0)
            # Release
            self.win32api.keybd_event(vk_code, scan_code, self.win32con.KEYEVENTF_KEYUP, 0)
        except:
            pass

    def play_pause(self):
        """Send Play/Pause media key"""
        self._send_key(0xB3)  # VK_MEDIA_PLAY_PAUSE

    def next_track(self):
        """Send Next Track media key"""
        self._send_key(0xB0)  # VK_MEDIA_NEXT_TRACK

    def prev_track(self):
        """Send Previous Track media key"""
        self._send_key(0xB1)  # VK_MEDIA_PREV_TRACK

    def stop(self):
        """Send Stop media key"""
        self._send_key(0xB2)  # VK_MEDIA_STOP


# ============================================================================
# WINDOW MANAGEMENT (using pywin32)
# ============================================================================

@dataclass
class WindowInfo:
    """Information about a window"""
    hwnd: int
    title: str
    is_visible: bool
    is_minimized: bool


class WindowManager:
    """Windows window management"""

    def __init__(self):
        self.available = False
        try:
            import win32gui
            import win32con
            import win32api
            self.win32gui = win32gui
            self.win32con = win32con
            self.win32api = win32api
            self.available = True
        except ImportError:
            print("[WARN] Window management not available (install pywin32)")
            self.available = False

    def get_visible_windows(self) -> List[WindowInfo]:
        """Get list of visible application windows"""
        if not self.available:
            return []

        windows = []

        def enum_callback(hwnd, results):
            if not self.win32gui.IsWindowVisible(hwnd):
                return

            title = self.win32gui.GetWindowText(hwnd)
            if not title:
                return

            # Filter out tool windows
            ex_style = self.win32gui.GetWindowLong(hwnd, self.win32con.GWL_EXSTYLE)
            if ex_style & self.win32con.WS_EX_TOOLWINDOW:
                return

            # Check if minimized
            placement = self.win32gui.GetWindowPlacement(hwnd)
            is_minimized = (placement[1] == self.win32con.SW_SHOWMINIMIZED)

            windows.append(WindowInfo(
                hwnd=hwnd,
                title=title,
                is_visible=True,
                is_minimized=is_minimized
            ))

        try:
            self.win32gui.EnumWindows(enum_callback, windows)
        except:
            pass

        return windows

    def activate_window(self, hwnd: int) -> bool:
        """Activate (bring to front) a window"""
        if not self.available:
            return False

        try:
            # Restore if minimized
            placement = self.win32gui.GetWindowPlacement(hwnd)
            if placement[1] == self.win32con.SW_SHOWMINIMIZED:
                self.win32gui.ShowWindow(hwnd, self.win32con.SW_RESTORE)

            # Bring to foreground
            self.win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to activate window: {e}")
            return False

    def snap_window_left(self):
        """Snap active window to left half"""
        if not self.available:
            return
        # Simulate Win+Left
        self._send_win_key(self.win32con.VK_LEFT)

    def snap_window_right(self):
        """Snap active window to right half"""
        if not self.available:
            return
        # Simulate Win+Right
        self._send_win_key(self.win32con.VK_RIGHT)

    def maximize_window(self):
        """Maximize active window"""
        if not self.available:
            return
        # Simulate Win+Up
        self._send_win_key(self.win32con.VK_UP)

    def show_desktop(self):
        """Show desktop (minimize all windows)"""
        if not self.available:
            return
        # Simulate Win+D
        self._send_win_key(0x44)  # 'D' key

    def _send_win_key(self, vk_code):
        """Send Windows key + another key"""
        try:
            # Press Win
            self.win32api.keybd_event(self.win32con.VK_LWIN, 0, 0, 0)
            # Press target key
            self.win32api.keybd_event(vk_code, 0, 0, 0)
            # Release target key
            self.win32api.keybd_event(vk_code, 0, self.win32con.KEYEVENTF_KEYUP, 0)
            # Release Win
            self.win32api.keybd_event(self.win32con.VK_LWIN, 0, self.win32con.KEYEVENTF_KEYUP, 0)
        except:
            pass


# ============================================================================
# SYSTEM API FACADE
# ============================================================================

class SystemAPI:
    """Unified interface for all system controls"""

    def __init__(self):
        self.volume = VolumeControl()
        self.media = MediaControl()
        self.windows = WindowManager()

    def is_available(self) -> bool:
        """Check if at least one API is available"""
        return (self.volume.available or
                self.media.available or
                self.windows.available)

    def get_status(self) -> dict:
        """Get status of all APIs"""
        return {
            'volume': self.volume.available,
            'media': self.media.available,
            'windows': self.windows.available
        }


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("Testing Windows API Integration...")
    api = SystemAPI()

    print("\nAPI Status:")
    for name, available in api.get_status().items():
        status = "[OK]" if available else "[WARN]"
        print(f"  {status} {name}")

    if api.volume.available:
        print(f"\nCurrent Volume: {api.volume.get_volume()}%")
        print(f"Muted: {api.volume.get_mute()}")

    if api.windows.available:
        windows = api.windows.get_visible_windows()
        print(f"\nVisible Windows: {len(windows)}")
        for i, win in enumerate(windows[:5], 1):
            print(f"  {i}. {win.title[:50]}")
