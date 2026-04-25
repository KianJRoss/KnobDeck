# Open Source Launch Roadmap

## Phase 1 (Now)
- Multi-keyboard profile registry (`python_host/device_profiles.py`)
- Plugin and firmware SDK templates (`sdk/`)
- GitHub Pages website (`docs-site/`)
- Windows build/installer pipeline (PyInstaller + Inno Setup)

## Phase 2
- Community profile submissions with CI validation
- Plugin marketplace index (signed metadata)
- Official board packs (Keychron / Glorious / Drop / MonsGeek)

## Phase 3
- Cross-platform host runtime (Windows first, Linux/macOS experimental)
- Optional Rust/Go service for lower-level HID reliability
- Telemetry-free crash reporting opt-in

## Governance
- Use PR templates for keyboard profiles, plugins, and firmware ports
- Require reproducible build notes for installer releases
- Keep plugin execution model explicit: trusted code only
