"""
path_utils.py — Centralized path resolution for PyInstaller .exe compatibility.

Two rules:
  - Read-only bundled assets  → get_resource_path()
  - Writable user data        → get_app_data_path()

Import and use these everywhere instead of os.getcwd(), os.path.dirname(__file__),
or bare relative paths.
"""
import os
import sys

# ── App name (folder inside %APPDATA%) ────────────────────────────────────────
_APP_FOLDER = "SparePartsPro_v1.5"


def get_resource_path(relative_path: str = "") -> str:
    """
    Resolve a path for READ-ONLY bundled assets (icons, SVGs, static DBs, etc.).

    • Frozen (.exe)  → sys._MEIPASS  (temporary extraction dir)
    • Development    → directory containing this file
    """
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = os.path.dirname(os.path.abspath(__file__))

    if relative_path:
        return os.path.join(base, relative_path)
    return base


def get_app_data_path(relative_path: str = "") -> str:
    """
    Resolve a path for WRITABLE user data (databases, invoices, logs, avatars, etc.).

    • Frozen (.exe)  → %APPDATA%/SparePartsPro_v1.5/<relative_path>
    • Development    → project root/<relative_path>

    The base directory is created automatically if it does not exist.
    """
    if getattr(sys, "frozen", False):
        base = os.path.join(
            os.environ.get("APPDATA") or os.path.expanduser("~"),
            _APP_FOLDER,
        )
    else:
        base = os.path.dirname(os.path.abspath(__file__))

    # Always ensure the base exists
    os.makedirs(base, exist_ok=True)

    if relative_path:
        full = os.path.join(base, relative_path)
        # Create parent directory for the requested path as well
        parent = os.path.dirname(full)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        return full
    return base
