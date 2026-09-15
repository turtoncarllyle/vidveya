from pathlib import Path
from unittest.mock import Mock
import uuid

import pytest

from vidveya import engine
from vidveya.models import UserError


@pytest.fixture
def download_stub(media_info, monkeypatch):
    selectors = []
    merged_bytes = b"original merged video and audio"

    class FakeYdl:
        def __init__(self, params):
            self.params = params
            self.format_selector = "WRONG_BEST"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def extract_info(self, url, download=False):
            return media_info

        def build_format_selector(self, selector):
            return selector

        def process_ie_result(self, info, download):
            selectors.append(self.format_selector)
            output = Path(self.params["outtmpl"].replace("%(ext)s", self.params["merge_output_format"]))
            output.write_bytes(merged_bytes)

    monkeypatch.setattr(engine.yt_dlp, "YoutubeDL", FakeYdl)
    monkeypatch.setattr(engine, "ydl_options", lambda *args: {})
    verify = Mock(return_value={"audio_channels": 2})
    monkeypatch.setattr(engine, "verify_media", verify)
    # 此处合并与校验已有替身，额外启动 FFmpeg 表示又引入了自动转码。
    monkeypatch.setattr("vidveya.media.subprocess.run", lambda *a, **kw: pytest.fail("不应自动转码"))
    return selectors, merged_bytes, verify


@pytest.mark.parametrize("option_key, codec, selector, resolution", [
    ("1280x720:30:mp4", "avc1.4d401f", "136+140", 720),
    ("1920x1080:30:mp4", "av01.0.08M.08", "399+140", 1080),
    ("1920x1080:30:mp4", "vp09.00.51.00", "399+140", 1080),
    ("1920x1080:30:webm", "vp9", "248+251", 1080),
])
def test_selected_streams_are_published_without_transcoding(
        download_stub, media_info, tmp_path, option_key, codec, selector, resolution):
    """检查实际选择器刷新、原编码合并结果及发布前的音视频校验。"""
    media_info["formats"] = [fmt for fmt in media_info["formats"] if fmt["format_id"] != "137"]
    next(fmt for fmt in media_info["formats"] if fmt["format_id"] == "399")["vcodec"] = codec
    selectors, merged_bytes, verify = download_stub
    events = []
    job_id = str(uuid.uuid4())
    result = engine.download({"url": "https://youtu.be/YE7VzlLtp-4", "job_id": job_id,
                              "directory": str(tmp_path), "option_key": option_key}, events.append)
    assert selectors == [selector]
    assert result["option"]["resolution"] == resolution
    assert result["option"]["video_codec"] == codec
    assert Path(result["path"]).read_bytes() == merged_bytes
    verify.assert_called_once_with(tmp_path / ".vidveya-tmp" / job_id / Path(result["path"]).with_stem("payload").name,
                                   resolution, 2.0)
    assert [event["state"] for event in events] == ["starting", "verifying"]


def test_missing_audio_fails_before_publishing(download_stub, tmp_path):
    _, _, verify = download_stub
    verify.side_effect = UserError("文件缺少有效的视频轨或音频轨")
    with pytest.raises(UserError, match="音频轨"):
        engine.download({"url": "https://youtu.be/YE7VzlLtp-4", "job_id": str(uuid.uuid4()),
                         "directory": str(tmp_path), "option_key": "1920x1080:30:mp4"}, lambda _: None)
    assert not list(tmp_path.rglob("*.mp4"))
    assert not list(tmp_path.rglob("*.completed.json"))
