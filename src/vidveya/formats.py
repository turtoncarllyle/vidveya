from typing import Any

from .models import FormatOption, UserError


def _codec(value: Any) -> bool:
    return bool(value and value != "none")


def _size(fmt: dict) -> int | None:
    value = fmt.get("filesize") or fmt.get("filesize_approx")
    return int(value) if value and value > 0 else None


def build_options(info: dict) -> list[FormatOption]:
    """Use yt-dlp's ascending quality order; never expose video-only output.

    Group by actual dimensions, FPS and container. YouTube's original format IDs
    remain internal; stable choice keys survive changes to signed stream URLs.
    """
    formats = [f for f in info.get("formats", []) if not f.get("has_drm")
               and f.get("format_id") and f.get("url")]
    audio = [f for f in formats if _codec(f.get("acodec")) and not _codec(f.get("vcodec"))]
    selected: dict[str, FormatOption] = {}
    for video in formats:
        if not _codec(video.get("vcodec")):
            continue
        width, height = int(video.get("width") or 0), int(video.get("height") or 0)
        if width <= 0 or height <= 0:
            continue
        container = video.get("ext")
        if container not in {"mp4", "webm"}:
            continue
        partner = None
        if not _codec(video.get("acodec")):
            extensions = {"m4a", "mp4"} if container == "mp4" else {"webm"}
            matches = [f for f in audio if f.get("ext") in extensions]
            if not matches:
                continue
            partner = matches[-1]
        size = _size(video)
        if partner:
            audio_size = _size(partner)
            size = size + audio_size if size and audio_size else None
        fps = float(video.get("fps") or 0)
        resolution = min(width, height)
        key = f"{width}x{height}:{fps:g}:{container}"
        option = FormatOption(
            key, resolution, width, height, fps, container, str(video["format_id"]),
            str(partner["format_id"]) if partner else None,
            str(video["vcodec"]), str((partner or video)["acodec"]), size,
        )
        previous = selected.get(key)
        # Prefer broadly playable H.264 at the SAME resolution/FPS. Higher
        # resolutions retain their original codec without expensive transcoding.
        if previous and previous.video_codec.startswith("avc") and not option.video_codec.startswith("avc"):
            continue
        selected[key] = option
    if not selected:
        raise UserError("未找到可下载的有声视频格式。视频可能受限或没有可用音频，请更换视频。")
    return sorted(selected.values(), key=lambda f: (-f.resolution, -f.fps, f.container != "mp4"))


def select_exact(options: list[FormatOption], key: str) -> FormatOption:
    for option in options:
        if option.key == key:
            return option
    raise UserError("所选清晰度或格式已不可用。请重新解析并选择；本次未降低清晰度。")
