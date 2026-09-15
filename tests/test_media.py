import subprocess

import pytest

from vidveya.media import NO_WINDOW, needs_compatible_mp4, tool, verify_media
from vidveya.models import UserError
from vidveya.paths import components_dir


def test_non_h264_mp4_uses_compatibility_conversion():
    assert needs_compatible_mp4("av01.0.08M.08", "mp4")
    assert needs_compatible_mp4("vp09.00.51.00", "mp4")
    assert not needs_compatible_mp4("avc1.640028", "mp4")
    assert not needs_compatible_mp4("av01.0.08M.08", "webm")


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    if not (components_dir() / "ffmpeg.exe").is_file():
        pytest.skip("Run scripts/provision.py to enable media integration tests")
    root = tmp_path_factory.mktemp("有声媒体")
    valid = root / "完整.mp4"
    silent = root / "无音轨.mp4"
    subprocess.run([str(tool("ffmpeg")), "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=24:d=2",
                    "-f", "lavfi", "-i", "sine=frequency=880:duration=2", "-c:v", "mpeg4", "-q:v", "8",
                    "-c:a", "aac", "-shortest", str(valid)], check=True, creationflags=NO_WINDOW)
    subprocess.run([str(tool("ffmpeg")), "-v", "error", "-i", str(valid), "-c:v", "copy", "-an", str(silent)],
                   check=True, creationflags=NO_WINDOW)
    return valid, silent


@pytest.mark.integration
def test_real_audio_video_tracks(clips):
    result = verify_media(clips[0], 360, 2)
    assert result["audio_channels"] > 0
    assert result["audio_codec"] == "aac"


@pytest.mark.integration
def test_silent_video_never_finishes_successfully(clips):
    with pytest.raises(UserError, match="音频轨"):
        verify_media(clips[1], 360, 2)


@pytest.mark.integration
def test_wrong_resolution_rejected(clips):
    with pytest.raises(UserError, match="清晰度"):
        verify_media(clips[0], 720, 2)


@pytest.mark.integration
def test_incomplete_duration_rejected(clips):
    with pytest.raises(UserError, match="时长"):
        verify_media(clips[0], 360, 25)
