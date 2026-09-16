import pytest

from vidveya import i18n


@pytest.fixture
def media_info():
    def fmt(fid, width=None, height=None, ext="mp4", video="avc1.4d401f", audio="none", size=1000, fps=30):
        return {"format_id": fid, "url": "https://example.invalid/media", "width": width, "height": height,
                "ext": ext, "vcodec": video, "acodec": audio, "filesize": size, "fps": fps}
    return {"id": "YE7VzlLtp-4", "title": "中文视频", "duration": 2, "formats": [
        fmt("140", ext="m4a", video="none", audio="mp4a.40.2", size=200),
        fmt("251", ext="webm", video="none", audio="opus", size=180),
        fmt("18", 640, 360, audio="mp4a.40.2"),
        fmt("136", 1280, 720), fmt("137", 1920, 1080),
        fmt("399", 1920, 1080, video="av01.0.08M.08"),
        fmt("248", 1920, 1080, ext="webm", video="vp9"),
        fmt("315", 3840, 2160, ext="webm", video="vp9", fps=60),
        fmt("short", 1080, 1920),
    ]}


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDVEYA_DATA_DIR", str(tmp_path / "appdata"))


@pytest.fixture(autouse=True)
def force_zh_language():
    """Force zh language for all tests so assertions on Chinese UI text pass
    regardless of the OS locale (e.g. GitHub Actions Windows runner uses en)."""
    original = i18n.get_current_language()
    i18n._CURRENT_LANG = "zh"
    yield
    i18n._CURRENT_LANG = original
