from __future__ import annotations

import sys
from importlib import resources
from importlib.resources import as_file
from pathlib import Path

from PySide6.QtGui import QIcon


def _icon_file_for_runtime() -> str:
    """
    Runtime icon path for Qt (use a PNG for widest compatibility).
    """
    # 1) wheel install / normal runtime
    try:
        p = resources.files("yimo.icons").joinpath("icon.png")
        with as_file(p) as real_path:
            return str(real_path)
    except Exception:
        pass

    # 2) dev run from source tree
    local = Path(__file__).resolve().parents[1] / "icons" / "icon.png"
    if local.exists():
        return str(local)

    # 3) PyInstaller
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        frozen = Path(meipass) / "yimo" / "icons" / "icon.png"
        if frozen.exists():
            return str(frozen)

    return ""


def load_app_icon() -> QIcon:
    path = _icon_file_for_runtime()
    return QIcon(path) if path else QIcon()
