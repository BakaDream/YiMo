import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator, Optional
from yimo.utils.constants import EXCLUDED_DIRS, TRANSLATABLE_EXTENSIONS, RESOURCE_EXTENSIONS

def is_excluded(path: Path) -> bool:
    """Check if the path is in the excluded list."""
    for part in path.parts:
        if part in EXCLUDED_DIRS:
            return True
    return False

def collect_files(root_dir: Path) -> Generator[Path, None, None]:
    """Recursively collect files from a directory, respecting exclusions."""
    root_path = Path(root_dir)
    for root, dirs, files in os.walk(root_path):
        # Modify dirs in-place to skip excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        
        for file in files:
            file_path = Path(root) / file
            if not is_excluded(file_path):
                yield file_path

def classify_file(file_path: Path) -> str:
    """
    Classify file as 'translate', 'resource', or 'ignore'.
    Returns: 'translate' | 'resource' | 'ignore'
    """
    suffix = file_path.suffix.lower()
    if suffix in TRANSLATABLE_EXTENSIONS:
        return 'translate'
    elif suffix in RESOURCE_EXTENSIONS:
        return 'resource'
    return 'ignore'

def copy_file(src: Path, dest: Path, stop_flag: Optional[object] = None):
    """Copy file ensuring parent directory exists.

    If stop_flag is provided and has an is_set() method, a stop request will
    prevent the final destination file from being replaced.
    """
    ensure_dir(dest.parent)
    if stop_flag is not None and getattr(stop_flag, "is_set", None) and stop_flag.is_set():
        return

    tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, dir=str(dest.parent), prefix=dest.name, suffix=".tmp") as tmp:
            tmp_path = Path(tmp.name)
        shutil.copy2(src, tmp_path)

        if stop_flag is not None and getattr(stop_flag, "is_set", None) and stop_flag.is_set():
            try:
                tmp_path.unlink()
            except Exception:
                pass
            return

        os.replace(tmp_path, dest)
    finally:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass

def read_file_content(path: Path) -> str:
    """Read text file content."""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file_content(path: Path, content: str, stop_flag: Optional[object] = None):
    """Write text content to file, ensuring parent directory exists.

    If stop_flag is provided and has an is_set() method, a stop request will
    prevent the final destination file from being replaced.
    """
    ensure_dir(path.parent)
    if stop_flag is not None and getattr(stop_flag, "is_set", None) and stop_flag.is_set():
        return

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)

        if stop_flag is not None and getattr(stop_flag, "is_set", None) and stop_flag.is_set():
            try:
                tmp_path.unlink()
            except Exception:
                pass
            return

        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass

def ensure_dir(path: Path):
    """Ensure the directory exists."""
    path.mkdir(parents=True, exist_ok=True)
