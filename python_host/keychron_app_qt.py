"""Backward-compatible shim for older imports.

Use `knobdeck_app_qt.py` as the canonical module.
"""

from knobdeck_app_qt import *  # noqa: F401,F403
from knobdeck_app_qt import main

if __name__ == "__main__":
    raise SystemExit(main())
