import importlib.metadata
import json
from pathlib import Path
import subprocess

from .models import UserError
from .paths import components_dir

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def needs_compatible_mp4(video_codec: str, container: str) -> bool:
    """Return whether a selected MP4 needs conversion for broad Windows playback."""
    if container.lower() != "mp4":
        return False
    codec = (video_codec or "").lower()
    return not codec.startswith(("avc", "h264"))


def transcode_compatible_mp4(source: Path, destination: Path) -> None:
    """Convert AV1/VP9 MP4 video to H.264 while copying the audio stream."""
    base = [str(tool("ffmpeg")), "-y", "-i", str(source), "-map", "0:v:0", "-map", "0:a:0",
            "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart"]
    attempts = [base + ["-c:v", "h264_mf", "-rate_control", "quality", "-quality", "90", str(destination)],
                base + ["-c:v", "libopenh264", "-profile:v", "high", "-b:v", "8M", str(destination)]]
    last_error = ""
    for command in attempts:
        destination.unlink(missing_ok=True)
        process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                 timeout=6 * 60 * 60, creationflags=NO_WINDOW)
        if process.returncode == 0 and destination.is_file() and destination.stat().st_size > 0:
            return
        last_error = (process.stderr or process.stdout or "FFmpeg 转换失败").strip()[-800:]
    destination.unlink(missing_ok=True)
    raise UserError("高清视频兼容转换失败：" + last_error)


def tool(name: str) -> Path:
    path = components_dir() / f"{name}.exe"
    if not path.is_file():
        raise UserError(f"内置 {name} 组件缺失。请重新完整解压便携包，或重新安装 VidVeya。")
    return path


def diagnostics() -> dict:
    result = {}
    for package in ("yt-dlp", "yt-dlp-ejs"):
        try:
            result[package] = {"ok": True, "version": importlib.metadata.version(package)}
        except importlib.metadata.PackageNotFoundError:
            result[package] = {"ok": False, "version": "组件缺失，请重新安装"}
    for name in ("ffmpeg", "ffprobe", "deno"):
        try:
            command = [str(tool(name)), "--version" if name == "deno" else "-version"]
            process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                     errors="replace", timeout=20, creationflags=NO_WINDOW)
            first_line = (process.stdout or process.stderr).splitlines()
            result[name] = {"ok": process.returncode == 0, "version": first_line[0][:180] if first_line else "无法启动"}
        except (UserError, OSError, subprocess.TimeoutExpired) as error:
            result[name] = {"ok": False, "version": str(error)}
    return result


def verify_media(path: Path, resolution: int, expected_duration: float | None = None) -> dict:
    if not path.is_file() or path.stat().st_size <= 0:
        raise UserError("下载文件不存在或为空，请重试。")
    command = [str(tool("ffprobe")), "-v", "error", "-show_entries",
               "stream=codec_type,codec_name,width,height,sample_rate,channels,duration:format=duration,size",
               "-of", "json", str(path)]
    process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=90, creationflags=NO_WINDOW)
    if process.returncode:
        raise UserError("文件校验失败：无法读取媒体内容。请重新下载。")
    try:
        info = json.loads(process.stdout)
        streams = info.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        if not video or not audio or int(audio.get("channels") or 0) <= 0 or int(audio.get("sample_rate") or 0) <= 0:
            raise UserError("文件缺少有效的视频轨或音频轨，本次下载未完成。请重试或更换格式。")
        if min(int(video.get("width") or 0), int(video.get("height") or 0)) != resolution:
            raise UserError("文件清晰度与选择不一致，本次下载未完成。请重新解析。")
        duration = float(info.get("format", {}).get("duration") or 0)
        if duration <= 0:
            raise UserError("文件时长无效，请重新下载。")
        if expected_duration and abs(duration - expected_duration) > max(3, expected_duration * 0.02):
            raise UserError("文件时长与源视频明显不同，可能下载不完整。请重试。")
        for stream in (video, audio):
            stream_duration = stream.get("duration")
            if stream_duration and stream_duration != "N/A" and abs(float(stream_duration) - duration) > max(3, duration * 0.02):
                raise UserError("音视频时长不匹配，可能下载不完整。请重试。")
        return {"duration": duration, "bytes": path.stat().st_size, "video_codec": video["codec_name"],
                "audio_codec": audio["codec_name"], "width": video["width"], "height": video["height"],
                "audio_channels": audio["channels"]}
    except (ValueError, KeyError, TypeError):
        raise UserError("文件校验结果无效，请重新下载。") from None
