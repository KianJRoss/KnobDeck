"""KnobDeck app entrypoint.

This wrapper keeps compatibility with the existing Qt runtime implementation
while exposing a neutral, non-vendor-specific launcher path.
"""

from __future__ import annotations

from knobdeck_app_qt import main


if __name__ == "__main__":
    raise SystemExit(main())
