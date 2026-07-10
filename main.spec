# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for shooter.

Produces a portable, one-directory build — no installer wrapper. This is
the layout Steam's SteamPipe expects to upload directly (it does its own
installing), and it starts faster than a onefile build since there's
nothing to self-extract to a temp dir on every launch.

Build:
    pyinstaller main.spec

Output:
    dist/shooter/        (Windows, Linux — run shooter/shooter[.exe])
    dist/shooter.app     (macOS)
"""
import sys

sys.path.insert(0, SPECPATH)
from version import APP_NAME, VERSION  # noqa: E402

from PyInstaller.utils.hooks import collect_submodules  # noqa: E402

block_cipher = None

hiddenimports = collect_submodules("websockets")

a = Analysis(
    ["main.py"],
    pathex=[SPECPATH],
    binaries=[],
    datas=[
        ("sounds", "sounds"),
        ("icon.png", "."),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if sys.platform == "win32":
    icon_file = "icon.ico"
elif sys.platform == "darwin":
    icon_file = "icon.icns"
else:
    icon_file = None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=icon_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=icon_file,
        bundle_identifier=f"com.ev4.{APP_NAME}",
        version=VERSION,
        info_plist={
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
        },
    )
