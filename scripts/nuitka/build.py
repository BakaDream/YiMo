from __future__ import annotations

import os
import platform
import shutil
import stat
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


def _nuitka_help_text() -> str:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "nuitka", "--help"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return proc.stdout or ""
    except Exception:
        return ""


def _supports_option(help_text: str, option_prefix: str) -> bool:
    return option_prefix in help_text


def _find_latest(paths: list[Path]) -> Path | None:
    if not paths:
        return None
    return max(paths, key=lambda p: p.stat().st_mtime)


def _copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _copy_app_bundle(src_app: Path, dest_app: Path) -> None:
    if dest_app.exists():
        shutil.rmtree(dest_app)
    dest_app.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src_app, dest_app, symlinks=True)


def _chmod_x(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _run_nuitka(cmd: list[str]) -> int:
    # Use a new session on POSIX so Ctrl-C interrupts this wrapper process first,
    # then we can terminate Nuitka without it dumping a long traceback.
    start_new_session = os.name != "nt"

    proc = subprocess.Popen(cmd, start_new_session=start_new_session)
    try:
        return int(proc.wait())
    except KeyboardInterrupt:
        print("Nuitka build interrupted by user.")
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        return 130


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    os.chdir(repo_root)

    os_name = _normalize_os_name(sys.platform)
    arch = _normalize_arch(platform.machine())

    entrypoint = repo_root / "main.py"
    if not entrypoint.exists():
        raise FileNotFoundError(f"Entrypoint not found: {entrypoint}")

    dist_dir = repo_root / "dist" / "nuitka" / f"{os_name}-{arch}"
    build_dir = repo_root / "build" / "nuitka" / f"{os_name}-{arch}"
    dist_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)

    help_text = _nuitka_help_text()
    use_mode_flag = _supports_option(help_text, "--mode=")

    common_args: list[str] = [
        sys.executable,
        "-m",
        "nuitka",
        f"--output-dir={build_dir}",
        "--assume-yes-for-downloads",
        "--enable-plugin=pyside6",
        "--include-package-data=yimo.gui.styles",
        "--include-package-data=yimo.icons",
    ]

    if _supports_option(help_text, "--jobs=") or _supports_option(help_text, "--jobs "):
        jobs = os.cpu_count() or 4
        common_args.append(f"--jobs={jobs}")

    if os_name in {"windows", "linux"}:
        if use_mode_flag:
            common_args.append("--mode=onefile")
        else:
            common_args.append("--onefile")
    elif os_name == "macos":
        # Some Nuitka versions disallow combining --mode=... with macOS app bundle options.
        # Use legacy standalone flags for widest compatibility.
        common_args.append("--standalone")

        if _supports_option(help_text, "--macos-create-app-bundle"):
            common_args.append("--macos-create-app-bundle")

        if _supports_option(help_text, "--macos-app-icon"):
            icns = repo_root / "src" / "yimo" / "icons" / "icon.icns"
            if icns.exists():
                common_args.append(f"--macos-app-icon={icns}")

        if _supports_option(help_text, "--macos-app-name"):
            common_args.append("--macos-app-name=YiMo")

        if _supports_option(help_text, "--macos-app-mode"):
            common_args.append("--macos-app-mode=gui")

    # Platform-specific flags
    if os_name == "windows":
        ico = repo_root / "src" / "yimo" / "icons" / "icon.ico"
        if ico.exists() and _supports_option(help_text, "--windows-icon-from-ico"):
            common_args.append(f"--windows-icon-from-ico={ico}")

        if _supports_option(help_text, "--windows-console-mode"):
            common_args.append("--windows-console-mode=disable")
        elif _supports_option(help_text, "--windows-disable-console"):
            common_args.append("--windows-disable-console")

    # Build
    return_code = _run_nuitka([*common_args, str(entrypoint)])
    if return_code != 0:
        if return_code != 130:
            print(f"Nuitka build failed with exit code {return_code}.")
        return return_code

    # Collect artifacts into stable dist paths
    if os_name == "windows":
        candidates = [p for p in build_dir.rglob("*.exe") if p.is_file()]
        artifact_src = _find_latest(candidates)
        if artifact_src is None:
            raise FileNotFoundError(f"Nuitka build finished but no .exe found under: {build_dir}")
        artifact = dist_dir / "yimo.exe"
        _copy_file(artifact_src, artifact)
    elif os_name == "linux":
        bin_candidates = [p for p in build_dir.rglob("*.bin") if p.is_file()]
        artifact_src = _find_latest(bin_candidates)
        if artifact_src is None:
            # Fallback: find any executable regular file.
            exec_candidates: list[Path] = []
            for p in build_dir.rglob("*"):
                if not p.is_file():
                    continue
                try:
                    if os.access(p, os.X_OK):
                        exec_candidates.append(p)
                except Exception:
                    continue
            artifact_src = _find_latest(exec_candidates)
        if artifact_src is None:
            raise FileNotFoundError(f"Nuitka build finished but no executable found under: {build_dir}")
        artifact = dist_dir / "yimo"
        _copy_file(artifact_src, artifact)
        _chmod_x(artifact)
    elif os_name == "macos":
        app_candidates = [p for p in build_dir.rglob("*.app") if p.is_dir()]
        app_src = _find_latest(app_candidates)
        if app_src is None:
            raise FileNotFoundError(f"Nuitka build finished but no .app bundle found under: {build_dir}")
        app_dest = dist_dir / "YiMo.app"
        _copy_app_bundle(app_src, app_dest)
        artifact = dist_dir / f"yimo-macos-{arch}.zip"
        _zip_macos_app(app_dest, artifact)
    else:
        raise RuntimeError(f"Unsupported platform for Nuitka packaging: {os_name}")

    if not artifact.exists():
        raise FileNotFoundError(f"Build succeeded but artifact not found: {artifact}")

    print(str(artifact.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
