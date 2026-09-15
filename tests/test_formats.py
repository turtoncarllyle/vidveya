import pytest

from vidveya.formats import build_options, select_exact
from vidveya.models import UserError


def test_sound_required_and_multiplexed_stream_is_preserved(media_info):
    options = build_options(media_info)
    assert all(item.audio_codec != "none" for item in options)
    assert next(item for item in options if item.resolution == 360).audio_id is None
    assert next(item for item in options if item.resolution == 720).selector == "136+140"


def test_same_quality_prefers_h264_not_av1(media_info):
    chosen = select_exact(build_options(media_info), "1920x1080:30:mp4")
    assert chosen.video_id == "137"
    assert chosen.estimated_bytes == 1200


def test_vertical_video_is_1080p(media_info):
    chosen = select_exact(build_options(media_info), "1080x1920:30:mp4")
    assert chosen.resolution == 1080


def test_container_pairing_and_4k_frame_rate(media_info):
    chosen = select_exact(build_options(media_info), "3840x2160:60:webm")
    assert chosen.audio_id == "251"
    assert chosen.fps == 60


def test_no_audio_rejected(media_info):
    media_info["formats"] = [f for f in media_info["formats"] if f["acodec"] == "none"]
    with pytest.raises(UserError, match="有声"):
        build_options(media_info)


def test_no_silent_resolution_fallback(media_info):
    with pytest.raises(UserError, match="未降低清晰度"):
        select_exact(build_options(media_info), "7680x4320:60:mp4")


def test_drm_and_unknown_dimensions_filtered(media_info):
    for fmt in media_info["formats"]:
        if fmt["vcodec"] != "none":
            fmt["has_drm"] = True
    with pytest.raises(UserError):
        build_options(media_info)
