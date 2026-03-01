from __future__ import annotations

import sys
from importlib import resources
from pathlib import Path


def load_stylesheet() -> str:
    """
    Load the bundled QSS theme.

    Priority:
    1) importlib.resources (wheel install)
    2) source tree next to this file (dev run)
    3) PyInstaller sys._MEIPASS (frozen app)
    """
    try:
        qss_path = resources.files("yimo.gui.styles").joinpath("light.qss")
        return qss_path.read_text(encoding="utf-8")
    except Exception:
        pass

    local_path = Path(__file__).resolve().parent / "styles" / "light.qss"
    if local_path.exists():
        return local_path.read_text(encoding="utf-8")

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        frozen_path = Path(meipass) / "yimo" / "gui" / "styles" / "light.qss"
        if frozen_path.exists():
            return frozen_path.read_text(encoding="utf-8")

    return ""

