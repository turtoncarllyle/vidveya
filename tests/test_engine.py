from pathlib import Path
import uuid

from vidveya import engine


def test_changing_selection_updates_compiled_selector(media_info, tmp_path, monkeypatch):
    """Regression: params['format'] alone left the original best selector cached."""
    selectors = []

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
            Path(self.params["outtmpl"].replace("%(ext)s", "mp4")).write_bytes(b"fake_media")

    monkeypatch.setattr(engine.yt_dlp, "YoutubeDL", FakeYdl)
    monkeypatch.setattr(engine, "ydl_options", lambda *args: {})
    monkeypatch.setattr(engine, "verify_media", lambda *args: {"audio_channels": 2})
    result = engine.download({"url": "https://youtu.be/YE7VzlLtp-4", "job_id": str(uuid.uuid4()),
                              "directory": str(tmp_path), "option_key": "1280x720:30:mp4"}, lambda _: None)
    assert selectors == ["136+140"]
    assert result["option"]["resolution"] == 720
    assert Path(result["path"]).is_file()
