"""
Voicemeeter API Integration

Wraps VoicemeeterRemote64.dll for controlling Voicemeeter Potato:
- Audio routing (strips to outputs A1/A2/A3)
- Gain control (strip volumes)
- Mute control
- Parameter get/set

Requirements:
    - Voicemeeter Potato installed
    - VoicemeeterRemote64.dll in system or specified path
"""

import ctypes
import os
import time
from typing import Optional, Callable, Dict, Any, List
from pathlib import Path


class VoicemeeterAPI:
    """Voicemeeter Remote API wrapper"""

    def __init__(self, dll_path: Optional[str] = None):
        self.dll = None
        self.logged_in = False

        # Function pointers
        self.login = None
        self.logout = None
        self.run_voicemeeter = None
        self.set_parameter_float = None
        self.get_parameter_float = None
        self.is_parameters_dirty = None
        self.set_parameter_string = None
        self.get_parameter_string = None

        # Try to load DLL
        self._load_dll(dll_path)

    def _load_dll(self, dll_path: Optional[str] = None):
        """Load VoicemeeterRemote64.dll"""
        # Default paths to try
        search_paths = []

        if dll_path:
            search_paths.append(dll_path)

        # Common installation paths
        search_paths.extend([
            r"C:\Program Files (x86)\VB\Voicemeeter\VoicemeeterRemote64.dll",
            r"C:\Program Files\VB\Voicemeeter\VoicemeeterRemote64.dll",
            os.path.join(os.getenv('ProgramFiles(x86)', ''), 'VB', 'Voicemeeter', 'VoicemeeterRemote64.dll'),
            os.path.join(os.getenv('ProgramFiles', ''), 'VB', 'Voicemeeter', 'VoicemeeterRemote64.dll'),
        ])

        # Try to load from each path
        for path in search_paths:
            if path and os.path.exists(path):
                try:
                    self.dll = ctypes.CDLL(path)
                    print(f"[OK] Loaded Voicemeeter DLL: {path}")
                    self._init_functions()
                    return
                except Exception as e:
                    print(f"[WARN] Failed to load {path}: {e}")
                    continue

        print("[WARN] Voicemeeter DLL not found - Voicemeeter features disabled")
        print("Install Voicemeeter Potato from: https://vb-audio.com/Voicemeeter/potato.htm")

    def _init_functions(self):
        """Initialize function pointers from DLL"""
        if not self.dll:
            return

        try:
            # Login / Logout
            self.login = self.dll.VBVMR_Login
            self.login.restype = ctypes.c_long

            self.logout = self.dll.VBVMR_Logout
            self.logout.restype = ctypes.c_long

            # Run Voicemeeter
            self.run_voicemeeter = self.dll.VBVMR_RunVoicemeeter
            self.run_voicemeeter.argtypes = [ctypes.c_long]
            self.run_voicemeeter.restype = ctypes.c_long

            # Set/Get parameters (float)
            self.set_parameter_float = self.dll.VBVMR_SetParameterFloat
            self.set_parameter_float.argtypes = [ctypes.c_char_p, ctypes.c_float]
            self.set_parameter_float.restype = ctypes.c_long

            self.get_parameter_float = self.dll.VBVMR_GetParameterFloat
            self.get_parameter_float.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_float)]
            self.get_parameter_float.restype = ctypes.c_long

            # Check if parameters are dirty
            self.is_parameters_dirty = self.dll.VBVMR_IsParametersDirty
            self.is_parameters_dirty.restype = ctypes.c_long

            # Set/Get parameters (string)
            self.set_parameter_string = self.dll.VBVMR_SetParameterStringA
            self.set_parameter_string.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
            self.set_parameter_string.restype = ctypes.c_long

            self.get_parameter_string = self.dll.VBVMR_GetParameterStringA
            self.get_parameter_string.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_char)]
            self.get_parameter_string.restype = ctypes.c_long

        except Exception as e:
            print(f"[ERROR] Failed to initialize Voicemeeter functions: {e}")
            self.dll = None

    def connect(self) -> bool:
        """Connect to Voicemeeter (login)"""
        if not self.dll or not self.login:
            return False

        try:
            result = self.login()
            if result == 0 or result == 1:
                # 0 = OK, 1 = OK but Voicemeeter was already running
                self.logged_in = True

                # Start Voicemeeter if not running (type 2 = Potato)
                if result == 1:
                    self.run_voicemeeter(2)
                    time.sleep(1.0)  # Wait for Voicemeeter to initialize

                print("[OK] Connected to Voicemeeter Potato")
                return True
            else:
                print(f"[ERROR] Voicemeeter login failed: {result}")
                return False

        except Exception as e:
            print(f"[ERROR] Voicemeeter connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from Voicemeeter (logout)"""
        if self.logged_in and self.logout:
            try:
                self.logout()
                self.logged_in = False
                print("[OK] Disconnected from Voicemeeter")
            except:
                pass

    def set_parameter(self, param: str, value: float) -> bool:
        """Set a Voicemeeter parameter

        Args:
            param: Parameter name (e.g., "Strip[0].Mute", "Strip[5].Gain", "Strip[0].A1")
            value: Value (0.0/1.0 for boolean, -60.0 to 12.0 for gain)

        Returns:
            True if successful
        """
        if not self.logged_in or not self.set_parameter_float:
            return False

        try:
            param_bytes = param.encode('ascii')
            result = self.set_parameter_float(param_bytes, ctypes.c_float(value))
            return result == 0
        except Exception as e:
            print(f"[ERROR] Failed to set parameter {param}: {e}")
            return False

    def get_parameter(self, param: str) -> Optional[float]:
        """Get a Voicemeeter parameter

        Args:
            param: Parameter name (e.g., "Strip[0].Mute")

        Returns:
            Parameter value or None if failed
        """
        if not self.logged_in or not self.get_parameter_float:
            return None

        try:
            # Removed the blocking loop on is_parameters_dirty.
            # Direct parameter retrieval is usually sufficient and faster.
            # If sync issues arise, this might be a place to re-evaluate.
            
            param_bytes = param.encode('ascii')
            value = ctypes.c_float()
            result = self.get_parameter_float(param_bytes, ctypes.byref(value))

            if result == 0:
                return value.value
            else:
                return None

        except Exception as e:
            print(f"[ERROR] Failed to get parameter {param}: {e}")
            return None

    def is_available(self) -> bool:
        """Check if Voicemeeter API is available"""
        return self.dll is not None and self.logged_in


class VoicemeeterConfig:
    """Voicemeeter strip/output configuration (Voicemeeter/Banana/Potato)."""
    def __init__(self):
        # Hardware Inputs (Stereo)
        self.MIC_STRIP = 0           # Strip 0: Microphone
        self.UNUSED_STRIPS = [1, 2, 3, 4]  # Strips 1-4: Unused hardware inputs

        # Virtual Inputs
        self.MAIN_STRIP = 5          # Strip 5: Main desktop audio
        self.MUSIC_STRIP = 6         # Strip 6: Music player
        self.COMM_STRIP = 7          # Strip 7: Communications (Discord)

        # Hardware Outputs
        self.OUTPUT_A1 = "A1"
        self.OUTPUT_A2 = "A2"
        self.OUTPUT_A3 = "A3"
        self.OUTPUT_A4 = "A4"
        self.OUTPUT_A5 = "A5"
        self.OUTPUT_B1 = "B1"
        self.OUTPUT_B2 = "B2"
        self.OUTPUT_B3 = "B3"
        self.ALL_OUTPUTS = [
            self.OUTPUT_A1, self.OUTPUT_A2, self.OUTPUT_A3, self.OUTPUT_A4, self.OUTPUT_A5,
            self.OUTPUT_B1, self.OUTPUT_B2, self.OUTPUT_B3
        ]
        self.OUTPUT_NAMES = {
            "A1": "Speakers",
            "A2": "Wired",
            "A3": "Wireless",
            "A4": "Alt 1",
            "A5": "Alt 2",
            "B1": "Virtual Out 1",
            "B2": "Virtual Out 2",
            "B3": "Virtual Out 3",
        }
        self.OUTPUT_ICONS = {
            "A1": "SPK",
            "A2": "WIR",
            "A3": "WLS",
            "A4": "A4",
            "A5": "A5",
            "B1": "B1",
            "B2": "B2",
            "B3": "B3",
        }
        self.VARIANT = "potato"  # voicemeeter | banana | potato
        self.ACTIVE_OUTPUTS = self._variant_default_outputs(self.VARIANT)

    def _variant_default_outputs(self, variant: str) -> List[str]:
        if variant == "voicemeeter":
            return [self.OUTPUT_A1, self.OUTPUT_A2, self.OUTPUT_B1]
        if variant == "banana":
            return [self.OUTPUT_A1, self.OUTPUT_A2, self.OUTPUT_A3, self.OUTPUT_B1, self.OUTPUT_B2]
        return list(self.ALL_OUTPUTS)

    def _variant_supported_outputs(self, variant: str) -> List[str]:
        return self._variant_default_outputs(variant)

    def _variant_max_strip(self, variant: str) -> int:
        if variant == "voicemeeter":
            return 2
        if variant == "banana":
            return 4
        return 7

    def as_dict(self) -> Dict[str, Any]:
        return {
            "mic_strip": int(self.MIC_STRIP),
            "main_strip": int(self.MAIN_STRIP),
            "music_strip": int(self.MUSIC_STRIP),
            "comm_strip": int(self.COMM_STRIP),
            "output_names": dict(self.OUTPUT_NAMES),
            "output_icons": dict(self.OUTPUT_ICONS),
            "variant": self.VARIANT,
            "active_outputs": list(self.ACTIVE_OUTPUTS),
        }

    def apply_overrides(self, data: Dict[str, Any]):
        if not isinstance(data, dict):
            return

        variant_before = self.VARIANT
        variant = str(data.get("variant", self.VARIANT)).strip().lower()
        if variant in ("voicemeeter", "banana", "potato"):
            self.VARIANT = variant

        max_strip = self._variant_max_strip(self.VARIANT)

        def _clamp_strip(value: Any, fallback: int) -> int:
            try:
                return max(0, min(max_strip, int(value)))
            except Exception:
                return fallback

        self.MIC_STRIP = _clamp_strip(data.get("mic_strip", self.MIC_STRIP), self.MIC_STRIP)
        self.MAIN_STRIP = _clamp_strip(data.get("main_strip", self.MAIN_STRIP), self.MAIN_STRIP)
        self.MUSIC_STRIP = _clamp_strip(data.get("music_strip", self.MUSIC_STRIP), self.MUSIC_STRIP)
        self.COMM_STRIP = _clamp_strip(data.get("comm_strip", self.COMM_STRIP), self.COMM_STRIP)

        output_names = data.get("output_names")
        if isinstance(output_names, dict):
            for out in self.ALL_OUTPUTS:
                if out in output_names:
                    value = str(output_names.get(out, "")).strip()
                    if value:
                        self.OUTPUT_NAMES[out] = value
        elif isinstance(output_names, list) and len(output_names) >= 3:
            # Backward compatibility with legacy A1/A2/A3 list format.
            self.OUTPUT_NAMES["A1"] = str(output_names[0]).strip() or self.OUTPUT_NAMES["A1"]
            self.OUTPUT_NAMES["A2"] = str(output_names[1]).strip() or self.OUTPUT_NAMES["A2"]
            self.OUTPUT_NAMES["A3"] = str(output_names[2]).strip() or self.OUTPUT_NAMES["A3"]

        output_icons = data.get("output_icons")
        if isinstance(output_icons, dict):
            for out in self.ALL_OUTPUTS:
                if out in output_icons:
                    value = str(output_icons.get(out, "")).strip()
                    if value:
                        self.OUTPUT_ICONS[out] = value
        elif isinstance(output_icons, list) and len(output_icons) >= 3:
            # Backward compatibility with legacy A1/A2/A3 list format.
            self.OUTPUT_ICONS["A1"] = str(output_icons[0]).strip() or self.OUTPUT_ICONS["A1"]
            self.OUTPUT_ICONS["A2"] = str(output_icons[1]).strip() or self.OUTPUT_ICONS["A2"]
            self.OUTPUT_ICONS["A3"] = str(output_icons[2]).strip() or self.OUTPUT_ICONS["A3"]

        active_outputs = data.get("active_outputs")
        if isinstance(active_outputs, list):
            allowed = set(self._variant_supported_outputs(self.VARIANT))
            normalized = [str(x).upper() for x in active_outputs if str(x).upper() in allowed]
            if normalized:
                canonical = [x for x in self.ALL_OUTPUTS if x in allowed]
                self.ACTIVE_OUTPUTS = [x for x in canonical if x in normalized]
        elif self.VARIANT != variant_before:
            self.ACTIVE_OUTPUTS = self._variant_default_outputs(self.VARIANT)

        if not self.ACTIVE_OUTPUTS:
            defaults = self._variant_default_outputs(self.VARIANT)
            self.ACTIVE_OUTPUTS = [defaults[0]] if defaults else [self.OUTPUT_A1]

    def get_outputs(self) -> List[str]:
        return list(self.ACTIVE_OUTPUTS)


class VoicemeeterController:
    """High-level Voicemeeter control interface"""

    def __init__(self):
        self.api = VoicemeeterAPI()
        self.config = VoicemeeterConfig()
        self._state_change_callback: Optional[Callable[[], None]] = None

    def set_state_change_callback(self, callback: Optional[Callable[[], None]]):
        """Register callback invoked after state-changing operations."""
        self._state_change_callback = callback

    def _notify_state_changed(self):
        if self._state_change_callback:
            try:
                self._state_change_callback()
            except Exception:
                # Avoid breaking control flow on persistence callback errors.
                pass

    def connect(self) -> bool:
        """Connect to Voicemeeter"""
        return self.api.connect()

    def disconnect(self):
        """Disconnect from Voicemeeter"""
        self.api.disconnect()

    def is_available(self) -> bool:
        """Check if Voicemeeter is available"""
        return self.api.is_available()

    def apply_profile(self, profile: Dict[str, Any]):
        """Apply user-defined Voicemeeter profile config."""
        self.config.apply_overrides(profile)

    # ========================================================================
    # MICROPHONE CONTROL
    # ========================================================================

    def get_mic_mute(self) -> bool:
        """Get microphone mute state"""
        value = self.api.get_parameter(f"Strip[{self.config.MIC_STRIP}].Mute")
        return bool(value) if value is not None else False

    def set_mic_mute(self, muted: bool, persist: bool = True) -> bool:
        """Set microphone mute state"""
        ok = self.api.set_parameter(f"Strip[{self.config.MIC_STRIP}].Mute", 1.0 if muted else 0.0)
        if ok and persist:
            self._notify_state_changed()
        return ok

    def toggle_mic_mute(self):
        """Toggle microphone mute"""
        self.set_mic_mute(not self.get_mic_mute())

    # ========================================================================
    # STRIP GAIN CONTROL
    # ========================================================================

    def get_strip_gain(self, strip: int) -> float:
        """Get strip gain in dB"""
        value = self.api.get_parameter(f"Strip[{strip}].Gain")
        return value if value is not None else 0.0

    def set_strip_gain(self, strip: int, gain_db: float, persist: bool = True) -> bool:
        """Set strip gain in dB (clamped to -60 to +12 dB)"""
        # Clamp to valid range
        clamped = max(-60.0, min(12.0, gain_db))
        ok = self.api.set_parameter(f"Strip[{strip}].Gain", clamped)
        if ok and persist:
            self._notify_state_changed()
        return ok

    def adjust_strip_gain(self, strip: int, delta_db: float):
        """Adjust strip gain by delta (clamped to -60 to +12 dB)"""
        current = self.get_strip_gain(strip)
        new_gain = current + delta_db
        # Clamp to valid range
        clamped = max(-60.0, min(12.0, new_gain))
        self.set_strip_gain(strip, clamped)

    # ========================================================================
    # ROUTING CONTROL
    # ========================================================================

    def get_routing(self, strip: int, output: str) -> bool:
        """Get strip routing to output (A1/A2/A3)"""
        value = self.api.get_parameter(f"Strip[{strip}].{output}")
        if value is None:
            return False
        # Voicemeeter returns 0.0 or 1.0
        return value > 0.5

    def set_routing(self, strip: int, output: str, enabled: bool, persist: bool = True) -> bool:
        """Set strip routing to output"""
        ok = self.api.set_parameter(f"Strip[{strip}].{output}", 1.0 if enabled else 0.0)
        if ok and persist:
            self._notify_state_changed()
        return ok

    def toggle_routing(self, strip: int, output: str):
        """Toggle strip routing to output"""
        current = self.get_routing(strip, output)
        target = not current

        # Apply and verify with short retries to avoid missed clicks.
        for _ in range(3):
            self.set_routing(strip, output, target)
            time.sleep(0.03)
            if self.get_routing(strip, output) == target:
                return

    # ========================================================================
    # STATE SNAPSHOT / RESTORE
    # ========================================================================

    def get_state(self) -> Dict[str, Any]:
        """Snapshot key Voicemeeter state used by this app."""
        outputs = self.config.get_outputs()

        def routing_for(strip: int) -> Dict[str, bool]:
            return {out: self.get_routing(strip, out) for out in outputs}

        return {
            "mic": {
                "mute": self.get_mic_mute(),
                "gain": self.get_strip_gain(self.config.MIC_STRIP),
                "routing": routing_for(self.config.MIC_STRIP),
            },
            "main": {
                "gain": self.get_strip_gain(self.config.MAIN_STRIP),
                "routing": routing_for(self.config.MAIN_STRIP),
            },
            "music": {
                "gain": self.get_strip_gain(self.config.MUSIC_STRIP),
                "routing": routing_for(self.config.MUSIC_STRIP),
            },
            "comm": {
                "gain": self.get_strip_gain(self.config.COMM_STRIP),
                "routing": routing_for(self.config.COMM_STRIP),
            },
        }

    def apply_state(self, state: Dict[str, Any]):
        """Apply previously saved app-managed Voicemeeter state."""
        if not state:
            return

        strip_map = {
            "mic": self.config.MIC_STRIP,
            "main": self.config.MAIN_STRIP,
            "music": self.config.MUSIC_STRIP,
            "comm": self.config.COMM_STRIP,
        }

        for key, strip in strip_map.items():
            section = state.get(key) or {}

            if "gain" in section:
                try:
                    self.set_strip_gain(strip, float(section["gain"]), persist=False)
                except (TypeError, ValueError):
                    pass

            routing = section.get("routing")
            if isinstance(routing, dict):
                for output in self.config.get_outputs():
                    if output in routing:
                        self.set_routing(strip, output, bool(routing[output]), persist=False)

            if key == "mic" and "mute" in section:
                self.set_mic_mute(bool(section["mute"]), persist=False)


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("Testing Voicemeeter API...")

    vm = VoicemeeterController()

    if vm.connect():
        print("\nVoicemeeter Status:")
        print(f"  Mic Mute: {vm.get_mic_mute()}")
        print(f"  Main Gain: {vm.get_strip_gain(vm.config.MAIN_STRIP):.1f} dB")
        print(f"  Music Gain: {vm.get_strip_gain(vm.config.MUSIC_STRIP):.1f} dB")
        print(f"  Comm Gain: {vm.get_strip_gain(vm.config.COMM_STRIP):.1f} dB")

        print("\nMain Audio Routing:")
        print(f"  A1 (Speakers): {vm.get_routing(vm.config.MAIN_STRIP, 'A1')}")
        print(f"  A2 (Wired): {vm.get_routing(vm.config.MAIN_STRIP, 'A2')}")
        print(f"  A3 (Wireless): {vm.get_routing(vm.config.MAIN_STRIP, 'A3')}")

        vm.disconnect()
    else:
        print("[ERROR] Failed to connect to Voicemeeter")
