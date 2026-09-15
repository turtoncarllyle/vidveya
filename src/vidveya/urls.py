import re
from urllib.parse import parse_qs, urlsplit

from .models import UserError

_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")


def normalize_url(value: str) -> str:
    value = value.strip()
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
            raise ValueError
        if parsed.port not in {None, 80, 443}:
            raise ValueError
        host = (parsed.hostname or "").lower()
        video_id = ""
        if host == "youtu.be":
            video_id = parsed.path.strip("/")
        elif host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
            if parsed.path == "/watch":
                ids = parse_qs(parsed.query).get("v", [])
                video_id = ids[0] if len(ids) == 1 else ""
            elif parsed.path.startswith("/shorts/"):
                video_id = parsed.path.removeprefix("/shorts/").rstrip("/")
        if not _VIDEO_ID.fullmatch(video_id):
            raise ValueError
    except ValueError:
        raise UserError("请粘贴有效的 YouTube 视频或 Shorts 链接。首版支持单个视频。") from None
    return f"https://www.youtube.com/watch?v={video_id}"


def validate_proxy(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https", "socks5", "socks5h"}
                or not parsed.hostname or not parsed.port or parsed.path not in {"", "/"}
                or parsed.query or parsed.fragment):
            raise ValueError
    except ValueError:
        raise UserError("代理格式应为 http://127.0.0.1:端口 或 socks5://127.0.0.1:端口。") from None
    return value
