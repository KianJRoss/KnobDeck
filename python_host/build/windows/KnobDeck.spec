# PyInstaller spec for KnobDeck Windows build

block_cipher = None

from pathlib import Path
project_root = Path.cwd()
app_root = project_root / "python_host"

a = Analysis(
    [str(app_root / "knobdeck_app.py")],
    pathex=[str(app_root)],
    binaries=[],
    datas=[
        (str(app_root / "themes.json"), "."),
        (str(app_root / "macro_layers.json"), "."),
        (str(app_root / "custom_context_commands.json"), "."),
        (str(app_root / "spin_up.png"), "."),
        (str(app_root / "spin_down.png"), "."),
        (str(app_root / "assets"), "assets"),
        (str(app_root / "plugins"), "plugins"),
        (str(app_root / "custom_plugins"), "custom_plugins"),
    ],
    hiddenimports=[
        "keyboard",
        "hid",
        "pystray",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "comtypes",
        "pycaw",
        "psutil",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KnobDeck",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(app_root / "assets" / "knobdeck.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="KnobDeck",
)
