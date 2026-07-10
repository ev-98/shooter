from __future__ import annotations
"""Filesystem paths that work both from source and from a frozen (PyInstaller) build.

PyInstaller extracts bundled data files to a temp dir and exposes it as
sys._MEIPASS; outside of a frozen build that attribute doesn't exist, so we
fall back to this file's own directory (the project root when run from source).
"""
import os
import sys

from version import APP_NAME


def resource_path(*parts: str) -> str:
    """Path to a bundled, read-only asset (icon, sounds, fonts)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def user_data_dir(app_name: str = APP_NAME) -> str:
    """Writable per-user directory for save data; created if missing.

    App bundles/Program Files are read-only (or prompt for elevation) once
    installed, so save data can't live next to the executable like it did
    in development.
    """
    if sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~/Library/Application Support"), app_name)
    elif sys.platform.startswith("win"):
        base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), app_name)
    else:
        base = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), app_name)
    os.makedirs(base, exist_ok=True)
    return base
