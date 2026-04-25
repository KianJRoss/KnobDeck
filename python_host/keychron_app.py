"""Backward-compatible shim for legacy script entry.

Use `knobdeck_legacy_app.py` as the canonical module.
"""

from knobdeck_legacy_app import *  # noqa: F401,F403
from knobdeck_legacy_app import main

if __name__ == "__main__":
    raise SystemExit(main())
