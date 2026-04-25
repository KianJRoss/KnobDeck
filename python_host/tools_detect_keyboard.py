"""Detect connected HID keyboards and suggest a KnobDeck profile snippet."""

from __future__ import annotations

import json

try:
    import hid  # type: ignore
except Exception as e:  # pragma: no cover
    raise SystemExit(f"hid module unavailable: {e}")


def main():
    devices = hid.enumerate()
    rows = []
    for d in devices:
        path = str(d.get("path", b""))
        usage_page = int(d.get("usage_page", 0) or 0)
        usage = int(d.get("usage", 0) or 0)
        if usage_page == 0 and usage == 0:
            continue
        rows.append(
            {
                "vendor_id": int(d.get("vendor_id", 0) or 0),
                "product_id": int(d.get("product_id", 0) or 0),
                "usage_page": usage_page,
                "usage": usage,
                "manufacturer_string": str(d.get("manufacturer_string", "")),
                "product_string": str(d.get("product_string", "")),
                "interface_number": d.get("interface_number"),
                "path": path,
            }
        )

    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
