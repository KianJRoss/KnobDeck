"""
SignalRGB control helpers for QMK-compatible keyboards.

Supports two control paths:
1) Keyboard raw HID commands used by the QMK SignalRGB bridge.
2) SignalRGB local REST API for effect browsing/switching.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

import hid


class SignalRGBController:
    """SignalRGB controller with raw HID and local API helpers."""

    CMD_ENABLE = 0x25
    CMD_DISABLE = 0x26

    def __init__(
        self,
        vendor_id: int,
        product_id: int,
        usage_page: int = 0xFF60,
        usage: int = 0x61,
        api_base_url: str = "http://localhost:16038",
        api_timeout_s: float = 1.0,
    ):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.usage_page = usage_page
        self.usage = usage
        self.api_base_url = api_base_url.rstrip("/")
        self.api_timeout_s = max(0.2, float(api_timeout_s))
        self._effects_cache: List[Dict[str, str]] = []
        # Cached desired keyboard lighting mode.
        # We default to SignalRGB-first behavior for this project.
        self.signalrgb_mode_enabled: Optional[bool] = True

    def _find_path(self) -> Optional[bytes]:
        for dev in hid.enumerate(self.vendor_id, self.product_id):
            if dev.get("usage_page") == self.usage_page and dev.get("usage") == self.usage:
                return dev.get("path")
        return None

    def _send(self, command: int) -> bool:
        dev = None
        try:
            path = self._find_path()
            if not path:
                return False

            dev = hid.device()
            dev.open_path(path)
            # [report_id][command][padding...]
            packet = bytes([0x00, command] + [0x00] * 30)
            dev.write(packet)
            return True
        except Exception:
            return False
        finally:
            if dev is not None:
                try:
                    dev.close()
                except Exception:
                    pass

    def enable_signalrgb_mode(self) -> bool:
        ok = self._send(self.CMD_ENABLE)
        if ok:
            self.signalrgb_mode_enabled = True
        return ok

    def disable_signalrgb_mode(self) -> bool:
        ok = self._send(self.CMD_DISABLE)
        if ok:
            self.signalrgb_mode_enabled = False
        return ok

    def pulse_enable(self) -> bool:
        """Disable then enable for a clean resync."""
        self.disable_signalrgb_mode()
        time.sleep(0.05)
        ok = self.enable_signalrgb_mode()
        if ok:
            self.signalrgb_mode_enabled = True
        return ok

    def toggle_lighting_mode(self) -> bool:
        """Toggle between SignalRGB and onboard/VIA keyboard lighting."""
        if self.signalrgb_mode_enabled:
            return self.disable_signalrgb_mode()
        return self.enable_signalrgb_mode()

    def get_mode_label(self) -> str:
        if self.signalrgb_mode_enabled:
            return "SignalRGB"
        return "Onboard/VIA"

    def sync_if_signalrgb_mode(self) -> bool:
        """Resync only when SignalRGB mode is currently selected."""
        if self.signalrgb_mode_enabled:
            return self.pulse_enable()
        return True

    @staticmethod
    def open_signalrgb() -> bool:
        """Try to open SignalRGB app."""
        try:
            subprocess.Popen(["cmd", "/c", "start", "", "signalrgb://"], shell=False)
            return True
        except Exception:
            pass

        known_paths = [
            r"C:\Program Files\WhirlwindFX\SignalRgb\SignalRgbLauncher.exe",
            r"C:\Program Files\WhirlwindFX\SignalRgb\SignalRgb.exe",
        ]
        for exe in known_paths:
            if os.path.exists(exe):
                try:
                    subprocess.Popen([exe], close_fds=True)
                    return True
                except Exception:
                    continue
        return False

    def _api_request(self, method: str, path: str, payload: Optional[Dict] = None) -> Optional[Dict]:
        """Call local SignalRGB API and parse JSON response."""
        url = f"{self.api_base_url}{path}"
        data = None
        headers = {}

        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, method=method.upper(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.api_timeout_s) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw) if raw else {}
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            return None

    @staticmethod
    def _ok(response: Optional[Dict]) -> bool:
        if not isinstance(response, dict):
            return False
        status = response.get("status")
        if isinstance(status, str):
            return status.lower() == "ok"
        # Some endpoints can still return useful data without explicit "status".
        return "errors" not in response

    def list_effects(self, force_refresh: bool = False) -> List[Dict[str, str]]:
        """Return installed SignalRGB effects as [{'id': str, 'name': str}, ...]."""
        if self._effects_cache and not force_refresh:
            return list(self._effects_cache)

        response = self._api_request("GET", "/api/v1/lighting/effects")
        if not self._ok(response):
            return list(self._effects_cache)

        items = (((response or {}).get("data") or {}).get("items") or [])
        parsed: List[Dict[str, str]] = []
        for item in items:
            effect_id = item.get("id")
            attrs = item.get("attributes") or {}
            name = attrs.get("name")
            if isinstance(effect_id, str) and isinstance(name, str):
                parsed.append({"id": effect_id, "name": name})

        if parsed:
            parsed.sort(key=lambda x: x["name"].lower())
            self._effects_cache = parsed

        return list(self._effects_cache)

    def apply_effect(self, effect_id: str) -> bool:
        if not effect_id:
            return False
        safe_id = urllib.parse.quote(effect_id, safe="")
        response = self._api_request("POST", f"/api/v1/lighting/effects/{safe_id}/apply")
        return self._ok(response)

    def apply_effect_by_name(self, effect_name: str) -> bool:
        """Lookup by name in cache/API and apply matching effect."""
        if not effect_name:
            return False

        effects = self.list_effects(force_refresh=False)
        if not effects:
            effects = self.list_effects(force_refresh=True)
        target = next((e for e in effects if e.get("name", "").lower() == effect_name.lower()), None)
        if not target:
            return False
        return self.apply_effect(target.get("id", ""))

    def apply_next_effect(self) -> Tuple[bool, Optional[str]]:
        response = self._api_request("POST", "/api/v1/lighting/next")
        if not self._ok(response):
            return False, None
        name = ((((response or {}).get("data") or {}).get("attributes") or {}).get("name"))
        return True, name if isinstance(name, str) else None

    def apply_previous_effect(self) -> Tuple[bool, Optional[str]]:
        response = self._api_request("POST", "/api/v1/lighting/previous")
        if not self._ok(response):
            return False, None
        name = ((((response or {}).get("data") or {}).get("attributes") or {}).get("name"))
        return True, name if isinstance(name, str) else None

    def apply_random_effect(self) -> Tuple[bool, Optional[str]]:
        effects = self.list_effects(force_refresh=False)
        if not effects:
            effects = self.list_effects(force_refresh=True)
        if not effects:
            return False, None
        selected = random.choice(effects)
        ok = self.apply_effect(selected.get("id", ""))
        return ok, selected.get("name") if ok else None
