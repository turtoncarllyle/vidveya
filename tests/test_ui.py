from vidveya.formats import build_options
from vidveya.store import Store
from vidveya.ui.window import MainWindow


def test_format_modes_and_busy_state(qtbot, tmp_path, media_info):
    store = Store(tmp_path / "ui.db")
    window = MainWindow(store, start_diagnostics=False)
    qtbot.addWidget(window)
    window.ready = True
    info = {"video_id": media_info["id"], "url": "https://youtu.be/YE7VzlLtp-4", "title": "<中文标题>",
            "channel": "频道", "duration": 2, "thumbnail": None,
            "options": [option.to_dict() for option in build_options(media_info)]}
    window.show_video(info)
    assert window.video_title.text() == "<中文标题>"
    assert all(item.resolution > 720 for item in window.visible_options)
    assert window.download_button.isEnabled()
    window.change_mode(0)
    assert all(item.resolution <= 720 for item in window.visible_options)
    window.downloader = object()
    window.update_actions()
    assert not window.download_button.isEnabled()
    window.downloader = None
    window.close()
    store.close()
