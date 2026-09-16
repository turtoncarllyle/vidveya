import ctypes
import os
from pathlib import Path
import re
import sys
import uuid


def data_dir() -> Path:
    override = os.environ.get("VIDVEYA_DATA_DIR")
    root = Path(override) if override else Path(os.environ.get("LOCALAPPDATA", Path.home())) / "VidVeya"
    root.mkdir(parents=True, exist_ok=True)
    return root


def downloads_dir() -> Path:
    if sys.platform == "win32":
        pointer = ctypes.c_wchar_p()
        guid = (ctypes.c_ubyte * 16).from_buffer_copy(uuid.UUID("374de290-123f-4565-9164-39c4925e467b").bytes_le)
        result = ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(pointer))
        if result == 0:
            try:
                return Path(pointer.value) / "VidVeya"
            finally:
                ctypes.windll.ole32.CoTaskMemFree(pointer)
    return Path.home() / "Downloads" / "VidVeya"


def resource_root() -> Path:
    return Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]


def components_dir() -> Path:
    if getattr(sys, "frozen", False):
        return resource_root() / "components"
    return resource_root() / ".tooling" / "runtime"


def asset_path(filename: str) -> Path:
    return resource_root() / "assets" / filename


def safe_name(title: str, video_id: str, resolution: int, extension: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip(" .")
    # Keep ample room for the directory and suffix on traditional Windows paths.
    cleaned = cleaned[:100].rstrip(" .") or "YouTube 视频"
    if cleaned.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))}:
        cleaned = "_" + cleaned
    return f"{cleaned} [{video_id}] {resolution}P.{extension}"


def publish_file(source: Path, directory: Path, filename: str) -> Path:
    """Windows rename is atomic and fails if the destination already exists."""
    desired = directory / filename
    for index in range(10000):
        target = desired if index == 0 else desired.with_stem(f"{desired.stem} ({index})")
        if target.exists():
            continue
        try:
            source.rename(target)
            return target
        except FileExistsError:
            continue
    raise OSError("同名文件过多，请更换保存目录。")
