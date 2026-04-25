"""
Keyboard device profile registry for multi-board support.

Profiles describe compatible knob keyboards and their HID/VIA capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Any

try:
    import hid  # type: ignore
except Exception:  # pragma: no cover
    hid = None


@dataclass(frozen=True)
class KeyboardProfile:
    id: str
    name: str
    vendor_id: int
    product_id: int
    usage_page: int = 0xFF60
    usage: int = 0x61
    qmk: bool = True
    via: bool = True
    signalrgb_ready: bool = False
    notes: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "vendor_id": self.vendor_id,
            "product_id": self.product_id,
            "usage_page": self.usage_page,
            "usage": self.usage,
            "qmk": self.qmk,
            "via": self.via,
            "signalrgb_ready": self.signalrgb_ready,
            "notes": self.notes,
        }


# Known baseline profiles. Additional community profiles can be added here.
KNOWN_PROFILES: List[KeyboardProfile] = [
    KeyboardProfile(
        id="default_qmk_knob",
        name="QMK Knob Board (Default)",
        vendor_id=0x3434,
        product_id=0x0311,
        usage_page=0xFF60,
        usage=0x61,
        qmk=True,
        via=True,
        signalrgb_ready=True,
        notes="Default fallback profile. Replace with device-specific profile if available.",
    ),
    KeyboardProfile(
        id="keychron_v1",
        name="Keychron V1",
        vendor_id=0x3434,
        product_id=0x0311,
        usage_page=0xFF60,
        usage=0x61,
        qmk=True,
        via=True,
        signalrgb_ready=True,
        notes="Primary validated profile in this repository.",
    ),
    KeyboardProfile(
        id="keychron_q1_pro",
        name="Keychron Q1 Pro",
        vendor_id=0x3434,
        product_id=0x0D03,
        usage_page=0xFF60,
        usage=0x61,
        qmk=True,
        via=True,
        signalrgb_ready=False,
        notes="QMK/VIA capable; verify exact PID by build/region before flashing.",
    ),
    KeyboardProfile(
        id="gmmk_pro",
        name="Glorious GMMK Pro",
        vendor_id=0x320F,
        product_id=0x5044,
        usage_page=0xFF60,
        usage=0x61,
        qmk=True,
        via=True,
        signalrgb_ready=False,
        notes="QMK/VIA supported; RGB/knob behavior can vary by firmware build.",
    ),
    KeyboardProfile(
        id="drop_sense75",
        name="Drop Sense75",
        vendor_id=0x04D8,
        product_id=0xEB21,
        usage_page=0xFF60,
        usage=0x61,
        qmk=True,
        via=True,
        signalrgb_ready=False,
        notes="QMK/VIA profile target; confirm VID/PID from detected device.",
    ),
    KeyboardProfile(
        id="keebio_bdn9",
        name="Keebio BDN9",
        vendor_id=0xCB10,
        product_id=0x1209,
        usage_page=0xFF60,
        usage=0x61,
        qmk=True,
        via=True,
        signalrgb_ready=False,
        notes="Encoder-focused macro pad; strong test platform for knob features.",
    ),
    KeyboardProfile(
        id="monsgeek_m1_qmk",
        name="MonsGeek M1 QMK",
        vendor_id=0xA8F8,
        product_id=0x0824,
        usage_page=0xFF60,
        usage=0x61,
        qmk=True,
        via=True,
        signalrgb_ready=False,
        notes="QMK/VIA capable. Confirm VID/PID from local device enumeration.",
    ),
]


def list_profiles() -> List[KeyboardProfile]:
    return list(KNOWN_PROFILES)


def get_profile(profile_id: str) -> Optional[KeyboardProfile]:
    needle = str(profile_id or "").strip().lower()
    for profile in KNOWN_PROFILES:
        if profile.id.lower() == needle:
            return profile
    return None


def find_profile_by_vid_pid(vendor_id: int, product_id: int) -> Optional[KeyboardProfile]:
    for profile in KNOWN_PROFILES:
        if profile.vendor_id == int(vendor_id) and profile.product_id == int(product_id):
            return profile
    return None


def detect_connected_profile() -> Optional[KeyboardProfile]:
    """Best-effort auto-detect against known VID/PID pairs."""
    if hid is None:
        return None
    try:
        devices = hid.enumerate()
    except Exception:
        return None

    for dev in devices:
        vid = int(dev.get("vendor_id", 0) or 0)
        pid = int(dev.get("product_id", 0) or 0)
        matched = find_profile_by_vid_pid(vid, pid)
        if matched:
            return matched
    return None
