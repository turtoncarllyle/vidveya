from dataclasses import asdict, dataclass
from typing import Any


class UserError(Exception):
    """An actionable error suitable for the desktop UI."""


@dataclass(frozen=True)
class FormatOption:
    key: str
    resolution: int
    width: int
    height: int
    fps: float
    container: str
    video_id: str
    audio_id: str | None
    video_codec: str
    audio_codec: str
    estimated_bytes: int | None

    @property
    def selector(self) -> str:
        return f"{self.video_id}+{self.audio_id}" if self.audio_id else self.video_id

    @property
    def label(self) -> str:
        suffix = {1440: " · 2K", 2160: " · 4K", 4320: " · 8K"}.get(self.resolution, "")
        return f"{self.resolution}P{suffix}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VideoInfo:
    video_id: str
    url: str
    title: str
    channel: str
    duration: float
    thumbnail: str | None
    options: list[FormatOption]
    availability: str = "public"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


ACTIVE_STATES = {"starting", "downloading", "merging", "converting", "verifying"}
STATE_LABELS = {
    "starting": "准备下载", "downloading": "正在下载", "merging": "正在合并",
    "converting": "正在转换为兼容 MP4", "verifying": "正在校验", "completed": "下载完成", "failed": "下载失败",
    "cancelled": "已取消", "interrupted": "已中断",
}
