from __future__ import annotations

import sys
import tempfile
from importlib import resources
from pathlib import Path


def _ensure_tmp_asset(name: str, content: bytes) -> Path:
    base = Path(tempfile.gettempdir()) / "yimo-assets"
    base.mkdir(parents=True, exist_ok=True)
    path = base / name
    if not path.exists() or path.stat().st_size == 0:
        path.write_bytes(content)
    return path


def load_stylesheet() -> str:
    """
    Load the bundled QSS theme.

    Priority:
    1) source tree / installed package next to this file
    2) PyInstaller sys._MEIPASS (frozen app)
    3) importlib.resources fallback (e.g. zip imports)
    """
    styles_dir = Path(__file__).resolve().parent / "styles"
    local_qss = styles_dir / "light.qss"
    if local_qss.exists():
        qss = local_qss.read_text(encoding="utf-8")
        chevron = (styles_dir / "chevron-down.svg").as_posix()
        return qss.replace("{CHEVRON_DOWN}", chevron)

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        frozen_dir = Path(meipass) / "yimo" / "gui" / "styles"
        frozen_qss = frozen_dir / "light.qss"
        frozen_chevron = frozen_dir / "chevron-down.svg"
        if frozen_qss.exists():
            qss = frozen_qss.read_text(encoding="utf-8")
            if frozen_chevron.exists():
                return qss.replace("{CHEVRON_DOWN}", frozen_chevron.as_posix())
            return qss

    try:
        qss_path = resources.files("yimo.gui.styles").joinpath("light.qss")
        qss = qss_path.read_text(encoding="utf-8")
        chevron_bytes = resources.files("yimo.gui.styles").joinpath("chevron-down.svg").read_bytes()
        chevron_path = _ensure_tmp_asset("chevron-down.svg", chevron_bytes)
        return qss.replace("{CHEVRON_DOWN}", chevron_path.as_posix())
    except Exception:
        pass

    return ""
