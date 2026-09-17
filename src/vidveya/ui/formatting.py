from ..i18n import t


def size_text(value):
    if value is None:
        return t("size_pending", "大小待确定")
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024


def duration_text(seconds):
    seconds = max(0, int(seconds or 0))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


def codec_text(codec):
    for prefix, name in (("avc", "H.264"), ("av01", "AV1"), ("vp9", "VP9"), ("vp09", "VP9"),
                         ("hev", "HEVC"), ("hvc", "HEVC")):
        if codec.startswith(prefix):
            return name
    return codec.split(".")[0]
