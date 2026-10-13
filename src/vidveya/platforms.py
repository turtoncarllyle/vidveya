"""Small operating-system adapters used by the desktop UI and worker."""
import os
from pathlib import Path
import subprocess
import sys


def ui_font_family() -> str:
    if sys.platform == "win32":
        return "Segoe UI"
    if sys.platform == "darwin":
        return "Helvetica Neue"
    return "Noto Sans"


def open_file(path: str | Path) -> None:
    target = str(path)
    if sys.platform == "win32":
        os.startfile(target)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", target])
    else:
        subprocess.Popen(["xdg-open", target])


def reveal_file(path: str | Path) -> None:
    target = str(path)
    if sys.platform == "win32":
        root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        subprocess.Popen([str(root / "explorer.exe"), "/select,", target])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", target])
    else:
        subprocess.Popen(["xdg-open", str(Path(target).parent)])
