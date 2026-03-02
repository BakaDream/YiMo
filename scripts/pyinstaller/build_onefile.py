from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path


def _normalize_os_name(sys_platform: str) -> str:
    if sys_platform.startswith("win"):
        return "windows"
    if sys_platform == "darwin":
        return "macos"
    if sys_platform.startswith("linux"):
        return "linux"
    return sys_platform


def _normalize_arch(machine: str) -> str:
    m = machine.lower()
    if m in {"x86_64", "amd64"}:
        return "x86_64"
    if m in {"arm64", "aarch64"}:
        return "arm64"
    return m


def _zip_macos_app(app_path: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ditto",
            "-c",
            "-k",
            "--sequesterRsrc",
            "--keepParent",
            str(app_path),
            str(zip_path),
        ],
        check=True,
    )


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    os.chdir(repo_root)

    os_name = _normalize_os_name(sys.platform)
    arch = _normalize_arch(platform.machine())

    app_name = "yimo"
    entrypoint = repo_root / "main.py"
    if not entrypoint.exists():
        raise FileNotFoundError(f"Entrypoint not found: {entrypoint}")

    dist_dir = repo_root / "dist" / "pyinstaller" / f"{os_name}-{arch}"
    work_dir = repo_root / "build" / "pyinstaller" / f"{os_name}-{arch}"
    spec_dir = repo_root / "build" / "pyinstaller" / f"{os_name}-{arch}"

    # PyInstaller warns that --onefile + macOS .app bundles clash with platform security
    # and will become an error in v7. Use onedir for macOS and zip the .app as a single artifact.
    mode_flag = "--onedir" if os_name == "macos" else "--onefile"
    data_sep = ";" if os_name == "windows" else ":"
    qss_src = repo_root / "src" / "yimo" / "gui" / "styles" / "light.qss"
    qss_dest = f"yimo{os.sep}gui{os.sep}styles"
    icons_src_dir = repo_root / "src" / "yimo" / "icons"
    icons_dest_dir = f"yimo{os.sep}icons"

    icon_path: Path | None = None
    if os_name == "windows":
        candidate = icons_src_dir / "icon.ico"
        icon_path = candidate if candidate.exists() else None
    elif os_name == "macos":
        candidate = icons_src_dir / "icon.icns"
        icon_path = candidate if candidate.exists() else None
    else:
        candidate = icons_src_dir / "icon.png"
        icon_path = candidate if candidate.exists() else None

    args: list[str] = [
        "--noconfirm",
        "--clean",
        "--log-level",
        "WARN",
        mode_flag,
        # Widgets-only app: exclude heavy/unused PySide6 modules and tooling.
        "--exclude-module",
        "PySide6.scripts",
        "--exclude-module",
        "PySide6.QtSql",
        "--exclude-module",
        "PySide6.QtQml",
        "--exclude-module",
        "PySide6.QtQuick",
        "--exclude-module",
        "PySide6.QtQuickWidgets",
        "--exclude-module",
        "PySide6.QtMultimedia",
        "--exclude-module",
        "PySide6.QtWebEngineCore",
        "--exclude-module",
        "PySide6.QtWebEngineWidgets",
        "--exclude-module",
        "PySide6.QtPdf",
        "--exclude-module",
        "PySide6.QtPdfWidgets",
        "--exclude-module",
        "PySide6.Qt3DCore",
        "--exclude-module",
        "PySide6.Qt3DRender",
        "--exclude-module",
        "PySide6.Qt3DInput",
        "--name",
        app_name,
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(spec_dir),
        "--paths",
        str(repo_root / "src"),
        "--add-data",
        f"{qss_src}{data_sep}{qss_dest}",
        "--add-data",
        f"{icons_src_dir}{data_sep}{icons_dest_dir}",
    ]

    if icon_path is not None:
        args += ["--icon", str(icon_path)]

    if os_name == "windows":
        args.append("--noconsole")
    if os_name == "macos":
        args.append("--windowed")

    from PyInstaller.__main__ import run as pyinstaller_run

    pyinstaller_run([*args, str(entrypoint)])

    if os_name == "windows":
        artifact = dist_dir / f"{app_name}.exe"
    elif os_name == "macos":
        app_bundle = dist_dir / f"{app_name}.app"
        if app_bundle.exists():
            artifact = dist_dir / f"{app_name}-{os_name}-{arch}.zip"
            _zip_macos_app(app_bundle, artifact)
        else:
            artifact = dist_dir / app_name
    else:
        artifact = dist_dir / app_name

    if not artifact.exists():
        raise FileNotFoundError(f"Build succeeded but artifact not found: {artifact}")

    # For CI usage.
    print(str(artifact))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
