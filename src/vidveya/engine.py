import json
import math
from pathlib import Path
import re
import shutil
import time
from typing import Callable
from urllib.parse import urlsplit
import uuid

import yt_dlp

from .auth import cookie_stream
from .formats import build_options, select_exact
from .media import needs_compatible_mp4, tool, transcode_compatible_mp4, verify_media
from .models import UserError, VideoInfo
from .paths import publish_file, safe_name
from .urls import normalize_url, validate_proxy

Emit = Callable[[dict], None]


class QuietLogger:
    def debug(self, message):
        pass

    def info(self, message):
        pass

    def warning(self, message):
        pass

    def error(self, message):
        pass  # yt-dlp also raises DownloadError; stdout is exclusively the protocol.


def friendly_error(error: Exception) -> str:
    if isinstance(error, UserError):
        return str(error)
    text = re.sub(r"\x1b\[[0-9;]*m", "", str(error))
    lowered = text.lower()
    if any(term in lowered for term in ("members-only", "members only", "join this channel", "subscriber-only", "available to this channel", "membership")):
        return "此视频需要对应频道的会员权限。请在设置中导入已加入该频道且有观看权限账号的 YouTube Cookie；已导入时请检查会员等级或刷新登录态。"
    if "private video" in lowered:
        return "这是私有视频。请导入被授权观看该视频的账号登录态后重试。"
    if any(term in lowered for term in ("age-restricted", "confirm your age", "age restricted")):
        return "此视频要求验证年龄。请在 YouTube 完成账号年龄验证，再导入该账号的有效 Cookie。"
    if any(term in lowered for term in ("not available in your country", "geo restricted", "geo-restricted", "not made this video available in your country")):
        return "此视频在当前地区不可用。请遵循视频的地区访问限制。"
    if any(term in lowered for term in ("cookies are no longer valid", "cookies have expired", "cookies are expired", "cookie")) and any(term in lowered for term in ("expired", "no longer valid", "invalid")):
        return "YouTube 登录态已失效，请在设置中清除并重新导入 Cookie。"
    if any(term in lowered for term in ("confirm you're not a bot", "sign in", "http error 403", "po token")):
        return "YouTube 暂时拒绝了访问，或该视频需要登录。请稍后重试、更换网络/代理或选择公开视频。"
    if "429" in text:
        return "YouTube 请求过于频繁，请稍后重试。"
    if any(term in lowered for term in ("timed out", "unable to download", "connection", "certificate", "proxy")):
        return "无法连接 YouTube。请检查网络；使用本地代理时，可在设置中填写代理地址。"
    if isinstance(error, PermissionError):
        return "无法写入保存目录，文件可能被占用。请选择其他文件夹。"
    if isinstance(error, OSError) and (error.errno == 28 or getattr(error, "winerror", None) == 112):
        return "磁盘空间不足，请释放空间或更换保存目录。"
    # Strip URLs (including credentials and signed query parameters) from UI errors.
    text = re.sub(r"https?://\S+", "[链接]", text)
    return "处理失败：" + text[:500]


def ydl_options(proxy: str = "", use_auth: bool = False) -> dict:
    tool("ffprobe")
    options = {
        "quiet": True, "no_warnings": True, "logger": QuietLogger(), "noprogress": True,
        "noplaylist": True, "socket_timeout": 25, "retries": 3, "fragment_retries": 3,
        "extractor_retries": 2, "ffmpeg_location": str(tool("ffmpeg").parent),
        "js_runtimes": {"deno": {"path": str(tool("deno"))}},
        "remote_components": set(), "proxy": validate_proxy(proxy) or None,
        "format": "bv*+ba/b", "overwrites": False,
    }
    if use_auth:
        options["cookiefile"] = cookie_stream()
    return options


def checked_info(ydl, url: str) -> dict:
    info = ydl.extract_info(normalize_url(url), download=False)
    if not isinstance(info, dict) or info.get("_type") in {"playlist", "multi_video"}:
        raise UserError("请提供单个视频链接。")
    if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming", "post_live"}:
        raise UserError("首版支持已发布的视频与 Shorts，暂不支持直播录制或尚未开始的视频。")
    if info.get("has_drm"):
        raise UserError("此视频的媒体格式不可下载。")
    if not info.get("duration") or info["duration"] <= 0:
        raise UserError("无法读取视频时长，请稍后重试或更换视频。")
    return info


def analyze(url: str, proxy: str = "", use_auth: bool = False) -> VideoInfo:
    canonical = normalize_url(url)
    with yt_dlp.YoutubeDL(ydl_options(proxy, use_auth)) as ydl:
        info = checked_info(ydl, canonical)
        thumbnail = info.get("thumbnail")
        if thumbnail:
            parsed = urlsplit(thumbnail)
            if parsed.scheme != "https" or parsed.hostname not in {"i.ytimg.com", "i9.ytimg.com", "img.youtube.com"}:
                thumbnail = None
        return VideoInfo(str(info["id"]), canonical, str(info.get("title") or "YouTube 视频"),
                         str(info.get("channel") or info.get("uploader") or "YouTube"),
                         float(info["duration"]), thumbnail, build_options(info), str(info.get("availability") or "public"))


def staging_dir(directory: Path, job_id: str) -> Path:
    if str(uuid.UUID(job_id)) != job_id:
        raise UserError("任务编号无效。")
    root = directory.resolve()
    staging = root / ".vidveya-tmp" / job_id
    if not staging.resolve().is_relative_to(root) or staging.is_symlink() or staging.parent.is_symlink():
        raise UserError("临时下载目录无效，请更换保存目录。")
    return staging


def cleanup_staging(directory: Path, job_id: str):
    target = staging_dir(directory, job_id)
    if target.is_dir():
        # Exact UUID-owned child of the chosen output directory, verified above.
        shutil.rmtree(target)
    try:
        target.parent.rmdir()
    except OSError:
        pass


def download(request: dict, emit: Emit) -> dict:
    url = normalize_url(request["url"])
    directory = Path(request["directory"]).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    stage = staging_dir(directory, request["job_id"])
    stage.mkdir(parents=True, exist_ok=True)
    last_emit = 0.0
    completed: dict[str, int] = {}
    totals: dict[str, int] = {}
    selected_ids: set[str] = set()

    def progress(event):
        nonlocal last_emit
        format_id = str(event.get("info_dict", {}).get("format_id", ""))
        current = int(event.get("downloaded_bytes") or 0)
        total = int(event.get("total_bytes") or event.get("total_bytes_estimate") or 0)
        if total:
            totals[format_id] = total
        completed[format_id] = current
        now = time.monotonic()
        if now - last_emit < 0.25 and event.get("status") != "finished":
            return
        last_emit = now
        known = bool(selected_ids) and all(totals.get(key, 0) > 0 for key in selected_ids)
        total_bytes = sum(totals.get(key, 0) for key in selected_ids) if known else None
        downloaded = sum(completed.values())
        percent = min(99, downloaded / total_bytes * 100) if total_bytes else None
        speed = event.get("speed")
        speed = float(speed) if speed and math.isfinite(speed) and speed > 0 else None
        emit({"event": "progress", "state": "downloading", "downloaded_bytes": downloaded,
              "total_bytes": total_bytes, "percent": percent, "speed": speed,
              "eta": (max(0, total_bytes - downloaded) / speed) if total_bytes and speed else None})

    def postprocess(event):
        if event.get("status") == "started":
            emit({"event": "progress", "state": "merging", "percent": None})

    try:
        options = ydl_options(request.get("proxy", ""), bool(request.get("use_auth")))
        options.update({"outtmpl": str(stage / "payload.%(ext)s"), "windowsfilenames": True,
                        "progress_hooks": [progress], "postprocessor_hooks": [postprocess]})
        with yt_dlp.YoutubeDL(options) as ydl:
            emit({"event": "progress", "state": "starting", "percent": None})
            info = checked_info(ydl, url)
            choice = select_exact(build_options(info), request["option_key"])
            free = shutil.disk_usage(directory).free
            storage_factor = 3.2 if needs_compatible_mp4(choice.video_codec, choice.container) else 2.15
            if choice.estimated_bytes and free < int(choice.estimated_bytes * storage_factor) + 64 * 1024 * 1024:
                raise UserError("磁盘空间不足以同时保存音视频和合并文件，请更换保存目录或释放空间。")
            selected_ids.update([choice.video_id] + ([choice.audio_id] if choice.audio_id else []))
            for fmt in info["formats"]:
                if str(fmt["format_id"]) in selected_ids:
                    totals[str(fmt["format_id"])] = int(fmt.get("filesize") or fmt.get("filesize_approx") or 0)
            ydl.params.update(format=choice.selector, merge_output_format=choice.container)
            # YoutubeDL compiles the selector at construction; changing params
            # alone would keep downloading its original "best" selection.
            ydl.format_selector = ydl.build_format_selector(choice.selector)
            ydl.process_ie_result(info, download=True)
        output = stage / f"payload.{choice.container}"
        if needs_compatible_mp4(choice.video_codec, choice.container):
            emit({"event": "progress", "state": "converting", "percent": None})
            compatible = stage / "payload.compat.mp4"
            transcode_compatible_mp4(output, compatible)
            output.unlink()
            compatible.replace(output)
        emit({"event": "progress", "state": "verifying", "percent": None})
        verification = verify_media(output, choice.resolution, float(info["duration"]))
        filename = safe_name(str(info.get("title") or "YouTube 视频"), str(info["id"]), choice.resolution, choice.container)
        final = publish_file(output, directory, filename)
        result = {"path": str(final), "title": str(info.get("title") or "YouTube 视频"),
                  "option": choice.to_dict(), "verification": verification}
        # A receipt bridges a crash between the final rename and the UI's SQLite commit.
        receipt = directory / ".vidveya-tmp" / f"{request['job_id']}.completed.json"
        receipt.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return result
    finally:
        cleanup_staging(directory, request["job_id"])
