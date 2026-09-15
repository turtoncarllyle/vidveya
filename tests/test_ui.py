from unittest.mock import Mock
import uuid

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from vidveya.formats import build_options
from vidveya.store import Store, timestamp
from vidveya.ui.window import MainWindow


@pytest.fixture
def make_window(qtbot, tmp_path, monkeypatch):
    windows = []

    def create():
        store = Store(tmp_path / "ui.db")
        window = MainWindow(store, start_diagnostics=False)
        # QtBot 的自动 close 会触发用户提示；此夹具统一走显式退出清理。
        windows.append(window)
        return window

    yield create
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    for window in reversed(windows):
        window.request_exit()
        window.store.close()
        window.deleteLater()


def start_fake_download(window, tmp_path):
    worker = Mock()
    worker.isRunning.return_value = True
    worker.wait.return_value = True
    window.workers.append(worker)
    window.downloader = worker
    window.current_job = {"id": str(uuid.uuid4()), "created": timestamp(), "title": "中文视频",
                          "state": "downloading", "directory": str(tmp_path),
                          "option": {"resolution": 1080, "container": "mp4"}}
    window.store.save_job(window.current_job)
    return worker


def respond_to_close(window, text, remember=False):
    def respond():
        dialog = window.findChild(QMessageBox)
        try:
            assert dialog is not None
            assert dialog.defaultButton().text() == "最小化"
            assert "下载会继续" in dialog.text()
            dialog.checkBox().setChecked(remember)
            next(control for control in dialog.buttons() if control.text() == text).click()
        finally:
            if dialog and dialog.isVisible():
                dialog.reject()
    QTimer.singleShot(0, respond)


def test_format_modes_and_busy_state(make_window, media_info):
    window = make_window()
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
    assert "需要播放器支持" in window.format_hint.text()
    assert "不重新编码" in window.formats.item(0, 0).toolTip()


def test_minimize_keeps_download_running(make_window, tmp_path, qtbot):
    window = make_window()
    window.store.set_setting("confirm_close", False)
    worker = start_fake_download(window, tmp_path)
    window.show()
    assert not window.close()
    qtbot.waitUntil(window.isMinimized)
    assert not window.closing
    worker.cancel.assert_not_called()
    worker.wait.assert_not_called()
    window.show_progress({"state": "merging", "percent": None})
    assert window.store.jobs()[0]["state"] == "merging"


def test_default_prompt_can_remember_minimize(make_window, qtbot):
    window = make_window()
    window.show()
    respond_to_close(window, "最小化", remember=True)
    assert not window.close()
    qtbot.waitUntil(window.isMinimized)
    assert window.store.get_setting("close_action") == "minimize"
    assert window.store.get_setting("confirm_close") is False
    assert not window.close_prompt_input.isChecked()


def test_cancelling_close_does_not_change_preferences(make_window):
    window = make_window()
    window.show()
    respond_to_close(window, "取消", remember=True)
    assert not window.close()
    assert window.isVisible() and not window.isMinimized()
    assert not window.closing
    assert window.store.get_setting("close_action", "minimize") == "minimize"
    assert window.store.get_setting("confirm_close", True) is True


def test_close_preferences_persist_and_exit_closes_window(make_window, tmp_path, monkeypatch):
    window = make_window()
    window.directory_input.setText(str(tmp_path / "我的视频"))
    window.close_action_input.setCurrentIndex(window.close_action_input.findData("exit"))
    window.close_prompt_input.setChecked(False)
    window.save_settings()
    assert "已保存" in window.settings_notice.text()
    window.request_exit()
    reopened = make_window()
    assert reopened.close_action_input.currentData() == "exit"
    assert not reopened.close_prompt_input.isChecked()
    monkeypatch.setattr(reopened, "ask_close_action", lambda _: pytest.fail("提示已经关闭"))
    reopened.show()
    assert reopened.close()
    assert reopened.closing and not reopened.isVisible()


def test_explicit_exit_bypasses_minimize_preference(make_window, monkeypatch):
    window = make_window()
    monkeypatch.setattr(window, "ask_close_action", lambda _: pytest.fail("显式退出不应询问最小化"))
    window.show()
    assert window.request_exit()
    assert window.closing and not window.isVisible()


def test_exit_confirms_and_interrupts_active_download(make_window, tmp_path, monkeypatch):
    window = make_window()
    window.store.set_setting("close_action", "exit")
    window.store.set_setting("confirm_close", False)
    worker = start_fake_download(window, tmp_path)
    window.show()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    assert not window.close()
    worker.cancel.assert_not_called()
    assert window.current_job["state"] == "downloading"
    assert not window.closing
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    assert window.close()
    worker.cancel.assert_called_once()
    worker.wait.assert_called_once()
    assert window.store.jobs()[0]["state"] == "interrupted"
    assert window.current_job is None


def test_declining_exit_does_not_remember_or_force_future_exit(make_window, tmp_path, monkeypatch):
    window = make_window()
    worker = start_fake_download(window, tmp_path)
    monkeypatch.setattr(window, "ask_close_action", lambda _: ("exit", True))
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    assert not window.close()
    assert window.store.get_setting("confirm_close", True) is True
    assert not window.request_exit()
    window.store.set_setting("confirm_close", False)
    assert not window.close()
    assert window.isMinimized()
    worker.cancel.assert_not_called()
