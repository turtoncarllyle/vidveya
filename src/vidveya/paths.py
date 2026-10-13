import ctypes
import os
import platform
from pathlib import Path
import re
import sys
import uuid


def runtime_platform() -> str:
    """Return the supported runtime identifier used by bundled components."""
    machine = platform.machine().lower()
    if sys.platform == "win32":
        return "windows-x64" if machine in {"amd64", "x86_64", "x64"} else "windows-unsupported"
    if sys.platform == "darwin":
        return "macos-arm64" if machine in {"arm64", "aarch64"} else "macos-x86_64"
    return f"{sys.platform}-{machine or 'unknown'}"


def executable_suffix() -> str:
    return ".exe" if sys.platform == "win32" else ""


def data_dir() -> Path:
    override = os.environ.get("VIDVEYA_DATA_DIR")
    if override:
        root = Path(override)
    elif sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "VidVeya"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / "VidVeya"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "VidVeya"
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


def component_executable(name: str) -> Path:
    path = components_dir() / f"{name}{executable_suffix()}"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def configure_component_environment(environment: dict[str, str] | None = None) -> dict[str, str]:
    """Return an environment that can load bundled native component libraries."""
    result = dict(os.environ if environment is None else environment)
    if sys.platform == "darwin":
        library_dir = components_dir() / "lib"
        if library_dir.is_dir():
            current = result.get("DYLD_LIBRARY_PATH", "")
            entries = [str(library_dir)] + ([current] if current else [])
            result["DYLD_LIBRARY_PATH"] = os.pathsep.join(entries)
    return result


if sys.platform == "darwin":
    # yt-dlp launches FFmpeg through inherited environment variables.
    os.environ.update(configure_component_environment())


def asset_path(filename: str) -> Path:
    return resource_root() / "assets" / filename


def safe_name(title: str, video_id: str, resolution: int, extension: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip(" .")
    # Keep ample room for the directory and suffix on traditional Windows paths.
    cleaned = cleaned[:100].rstrip(" .") or "YouTube 视频"
    if sys.platform == "win32" and cleaned.split(".")[0].upper() in {
        "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))
    }:
        cleaned = "_" + cleaned
    return f"{cleaned} [{video_id}] {resolution}P.{extension}"


def publish_file(source: Path, directory: Path, filename: str) -> Path:
    """Publish without overwriting an existing file on any supported platform."""
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
