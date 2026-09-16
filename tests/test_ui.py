from unittest.mock import Mock
import uuid

import pytest
from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtWidgets import QListView, QMenu, QMessageBox

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


def test_download_progress_shows_percentage_speed_and_eta(make_window, tmp_path):
    window = make_window()
    start_fake_download(window, tmp_path)
    window.show_progress({"state": "downloading", "percent": 47.5, "downloaded_bytes": 47.5 * 1024**2,
                          "total_bytes": 100 * 1024**2, "speed": 3 * 1024**2, "eta": 17})
    assert window.progress_value.text() == "47%"
    assert window.progress_bar.value() == 47
    assert window.progress_bar.maximum() == 100
    assert "47.5 MB / 100.0 MB" in window.progress_meta.text()
    assert "3.0 MB/s" in window.progress_meta.text()
    assert "剩余 0:17" in window.progress_meta.text()


@pytest.mark.parametrize("state, caption", [("downloading", "下载中"), ("merging", "合并中"), ("verifying", "校验中")])
def test_unknown_percentage_displays_phase_without_fake_completion(make_window, tmp_path, state, caption):
    window = make_window()
    start_fake_download(window, tmp_path)
    window.show_progress({"state": "downloading", "percent": 75})
    window.show_progress({"state": state, "percent": None, "downloaded_bytes": 1024**2})
    assert window.progress_value.text() == caption
    assert window.progress_bar.minimum() == window.progress_bar.maximum() == 0
    if state == "downloading":
        assert "总大小待确定" in window.progress_meta.text()
        assert "1.0 MB" in window.progress_meta.text()


def test_progress_only_reaches_100_after_verified_result(make_window, tmp_path):
    window = make_window()
    start_fake_download(window, tmp_path)
    window.show_progress({"state": "downloading", "percent": 100})
    assert window.progress_value.text() == "99%"
    window.download_done({"path": str(tmp_path / "有声视频.mp4"), "verification": {"bytes": 1024}})
    assert window.progress_value.text() == "100%"
    assert window.progress_bar.value() == 100
    assert window.store.jobs()[0]["state"] == "completed"


def test_theme_toggle_and_persistence(make_window):
    window = make_window()
    initial_theme = window.current_theme_setting
    assert initial_theme in {"system", "light", "dark"}
    window.toggle_theme_quick()
    assert window.store.get_setting("theme") in {"light", "dark"}
    window.apply_theme("dark")
    assert window.current_theme_setting == "dark"
    window.apply_theme("light")
    assert window.current_theme_setting == "light"


def test_language_switch_and_i18n():
    from vidveya.i18n import get_current_language, set_language, t
    assert set_language("en") == "en"
    assert get_current_language() == "en"
    assert t("dl_btn_download") == "Download Selected"
    assert set_language("zh") == "zh"
    assert get_current_language() == "zh"
    assert t("dl_btn_download") == "下载所选视频"


def test_sidebar_mini_task_lifecycle(make_window, tmp_path):
    window = make_window()
    assert window.sidebar_mini_task.isHidden()
    start_fake_download(window, tmp_path)
    window.show_progress({"state": "downloading", "percent": 50})
    assert not window.sidebar_mini_task.isHidden()
    assert window.mini_status.text() == "50%"
    window.download_done({"path": str(tmp_path / "有声视频.mp4"), "verification": {"bytes": 1024}})
    assert window.sidebar_mini_task.isHidden()


def test_cookie_help_dialog(make_window, monkeypatch):
    window = make_window()
    dialog_opened = []

    def fake_exec(self):
        dialog_opened.append(self.windowTitle())
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    window.show_cookie_help()
    assert len(dialog_opened) == 1
    assert "Cookie" in dialog_opened[0]


def test_combobox_uses_qlistview(make_window):
    from PySide6.QtWidgets import QListView
    window = make_window()
    for combo in (window.theme_input, window.language_input, window.close_action_input, window.sort_combo):
        assert isinstance(combo.view(), QListView)


def test_no_exit_button_in_sidebar(make_window):
    window = make_window()
    assert not hasattr(window, "exit_button")
    assert hasattr(window, "request_exit")


def test_combobox_view_and_container_properties(make_window):
    from PySide6.QtCore import Qt
    window = make_window()
    for combo in (window.theme_input, window.language_input, window.close_action_input):
        view = combo.view()
        assert isinstance(view, QListView)
        assert view.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        container = view.parentWidget()
        if container:
            assert bool(container.windowFlags() & Qt.WindowType.FramelessWindowHint)
            assert container.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)


def test_local_datetime_formatting_no_utc():
    from vidveya.ui.window import format_local_datetime
    utc_str = "2026-09-15T09:30:00+00:00"
    formatted = format_local_datetime(utc_str)
    assert "UTC" not in formatted
    assert "-" in formatted
    assert ":" in formatted
    assert len(formatted) == 19


def test_history_sorting_and_rendering(make_window):
    window = make_window()
    job1 = {
        "id": "job-1",
        "created": "2026-09-15T01:00:00+00:00",
        "title": "Beta Video",
        "url": "https://youtube.com/watch?v=1",
        "state": "completed",
        "option": {"resolution": "1080", "container": "mp4"},
    }
    job2 = {
        "id": "job-2",
        "created": "2026-09-15T02:00:00+00:00",
        "title": "Alpha Video",
        "url": "https://youtube.com/watch?v=2",
        "state": "completed",
        "option": {"resolution": "720", "container": "mp4"},
    }
    window.store.save_job(job1)
    window.store.save_job(job2)
    window.refresh_history()
    assert window.history.rowCount() == 2

    # 默认创建时间倒序 (最新在前: job2)
    assert window.history.item(0, 0).text() == "Alpha Video"
    assert window.history.item(1, 0).text() == "Beta Video"

    # 切换为创建时间正序 (最早在前: job1)
    idx_asc = window.sort_combo.findData("date_asc")
    window.sort_combo.setCurrentIndex(idx_asc)
    assert window.history.item(0, 0).text() == "Beta Video"
    assert window.history.item(1, 0).text() == "Alpha Video"

    # 切换为视频名称正序 (Alpha 在前)
    idx_name_asc = window.sort_combo.findData("name_asc")
    window.sort_combo.setCurrentIndex(idx_name_asc)
    assert window.history.item(0, 0).text() == "Alpha Video"
    assert window.history.item(1, 0).text() == "Beta Video"

    # 切换为视频名称倒序 (Beta 在前)
    idx_name_desc = window.sort_combo.findData("name_desc")
    window.sort_combo.setCurrentIndex(idx_name_desc)
    assert window.history.item(0, 0).text() == "Beta Video"
    assert window.history.item(1, 0).text() == "Alpha Video"


def test_history_delete_and_clear(make_window, monkeypatch):
    window = make_window()
    job1 = {
        "id": "job-1",
        "created": "2026-09-15T01:00:00+00:00",
        "title": "Video 1",
        "url": "https://youtube.com/watch?v=1",
        "state": "completed",
        "option": {"resolution": "1080", "container": "mp4"},
    }
    job2 = {
        "id": "job-2",
        "created": "2026-09-15T02:00:00+00:00",
        "title": "Video 2",
        "url": "https://youtube.com/watch?v=2",
        "state": "completed",
        "option": {"resolution": "1080", "container": "mp4"},
    }
    window.store.save_job(job1)
    window.store.save_job(job2)
    window.refresh_history()
    assert window.history.rowCount() == 2

    # 选中第一行并删除
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    window.history.selectRow(0)
    window.delete_selected()
    assert window.history.rowCount() == 1

    # 清空所有记录
    window.clear_all_history()
    assert window.history.rowCount() == 0
    assert len(window.store.jobs()) == 0


@pytest.mark.parametrize("action", ["delete_selected", "clear_all_history"])
def test_history_actions_protect_an_ongoing_download(make_window, tmp_path, monkeypatch, action):
    window = make_window()
    worker = start_fake_download(window, tmp_path)
    active_id = window.current_job["id"]
    video = tmp_path / "已下载的视频.mp4"
    video.write_bytes(b"keep downloaded media")
    window.store.save_job({"id": "finished", "state": "completed", "created": timestamp(),
                           "title": "已完成", "option": {}, "result": {"path": str(video)}})
    window.refresh_history()
    active_row = next(i for i, job in enumerate(window.display_jobs) if job["id"] == active_id)
    window.history.selectRow(active_row)
    assert not window.delete_history_button.isEnabled()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    getattr(window, action)()

    assert active_id in {job["id"] for job in window.store.jobs()}
    if action == "clear_all_history":
        assert len(window.store.jobs()) == 1
        assert not window.clear_history_button.isEnabled()
    assert video.read_bytes() == b"keep downloaded media"
    worker.cancel.assert_not_called()
    window.show_progress({"state": "merging", "percent": None})
    assert next(job for job in window.store.jobs() if job["id"] == active_id)["state"] == "merging"
    window.download_done({"path": str(video), "verification": {"bytes": video.stat().st_size}})
    assert next(job for job in window.store.jobs() if job["id"] == active_id)["state"] == "completed"
    assert window.progress_bar.value() == 100


def test_context_menu_keeps_target_while_worker_refreshes_history(make_window, monkeypatch):
    window = make_window()
    target = {"id": "target", "title": "Original", "state": "completed", "option": {},
              "created": "2026-09-15T01:00:00+00:00"}
    window.store.save_job(target)
    window.refresh_history()
    monkeypatch.setattr(window.history, "itemAt", lambda pos: window.history.item(0, 0))
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    opened = []

    def open_menu(menu, pos):
        opened.append(True)
        window.store.save_job({**target, "id": "newer", "created": "2026-09-15T02:00:00+00:00"})
        window.refresh_history()
        menu.actions()[-1].trigger()

    menu = QMenu(window)
    monkeypatch.setattr("vidveya.ui.window.QMenu", lambda parent: menu)
    monkeypatch.setattr(menu, "exec", lambda pos: open_menu(menu, pos))
    window.show_history_context_menu(QPoint(1, 1))
    assert opened == [True]
    assert [job["id"] for job in window.store.jobs()] == ["newer"]


def test_active_history_context_menu_disables_deletion(make_window, tmp_path, monkeypatch):
    window = make_window()
    start_fake_download(window, tmp_path)
    window.refresh_history()
    monkeypatch.setattr(window.history, "itemAt", lambda pos: window.history.item(0, 0))
    enabled = []
    menu = QMenu(window)
    monkeypatch.setattr("vidveya.ui.window.QMenu", lambda parent: menu)
    monkeypatch.setattr(menu, "exec", lambda pos: enabled.append(menu.actions()[-1].isEnabled()))
    window.show_history_context_menu(QPoint(1, 1))
    assert enabled == [False]


def test_history_selection_survives_sort_and_refresh(make_window, monkeypatch):
    window = make_window()
    for number, title in enumerate(("Beta", "Alpha"), start=1):
        window.store.save_job({"id": str(number), "title": title, "state": "completed", "option": {},
                               "created": f"2026-09-15T0{number}:00:00+00:00"})
    window.refresh_history()
    window.history.selectRow(0)
    assert window.selected_job()["id"] == "2"

    window.sort_combo.setCurrentIndex(window.sort_combo.findData("date_asc"))
    assert window.selected_job()["id"] == "2"
    window.store.save_job({"id": "older", "title": "Earlier", "state": "completed", "option": {},
                           "created": "2026-09-15T00:00:00+00:00"})
    window.refresh_history()
    assert window.selected_job()["id"] == "2"

    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    window.delete_selected()
    assert {job["id"] for job in window.store.jobs()} == {"1", "older"}
    assert window.selected_job() is None
    assert not window.delete_history_button.isEnabled()


@pytest.mark.parametrize("column, expected, first_order", [
    (0, ["b", "c", "a"], Qt.SortOrder.AscendingOrder),
    (1, ["c", "b", "a"], Qt.SortOrder.DescendingOrder),
    (2, ["c", "b", "a"], Qt.SortOrder.AscendingOrder),
    (3, ["a", "c", "b"], Qt.SortOrder.AscendingOrder),
])
def test_history_header_clicks_sort_and_keep_selected_task(make_window, qtbot, column, expected, first_order):
    window = make_window()
    for job_id, title, resolution, state, hour in [
        ("a", "Zulu", 720, "failed", 1),
        ("b", "Alpha", 1080, "completed", 3),
        ("c", "Beta", 2160, "downloading", 2),
    ]:
        window.store.save_job({"id": job_id, "title": title, "state": state,
                               "option": {"resolution": resolution, "container": "mp4"},
                               "created": f"2026-09-15T0{hour}:00:00+00:00"})
    window.refresh_history()
    window.pages.setCurrentIndex(1)
    window.show()
    qtbot.wait(50)
    window.history.selectRow(1)
    assert window.selected_job()["id"] == "c"
    assert window.sort_combo.isHidden()
    header = window.history.horizontalHeader()
    assert header.sectionsClickable()
    assert header.isSortIndicatorShown()
    assert header.cursor().shape() == Qt.CursorShape.PointingHandCursor
    point = QPoint(header.sectionViewportPosition(column) + header.sectionSize(column) // 2,
                   header.height() // 2)
    qtbot.mouseClick(header.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert [job["id"] for job in window.display_jobs] == expected
    assert header.sortIndicatorSection() == column
    assert header.sortIndicatorOrder() == first_order
    arrow = "▲" if first_order == Qt.SortOrder.AscendingOrder else "▼"
    assert window.history.horizontalHeaderItem(column).text().endswith(arrow)
    assert window.selected_job()["id"] == "c"
    assert not window.delete_history_button.isEnabled()

    qtbot.mouseClick(header.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert [job["id"] for job in window.display_jobs] == list(reversed(expected))
    assert header.sortIndicatorOrder() != first_order
    reversed_arrow = "▼" if first_order == Qt.SortOrder.AscendingOrder else "▲"
    assert window.history.horizontalHeaderItem(column).text().endswith(reversed_arrow)
    assert window.selected_job()["id"] == "c"
    window.refresh_history()
    assert [job["id"] for job in window.display_jobs] == list(reversed(expected))
    assert window.selected_job()["id"] == "c"


def test_qt_translator_and_standard_dialog_buttons():
    from PySide6.QtWidgets import QApplication, QMessageBox
    from vidveya.i18n import install_qt_translator, set_language
    app = QApplication.instance() or QApplication([])
    
    # Switch to zh
    set_language("zh")
    assert install_qt_translator(app, "zh") is True
    box_zh = QMessageBox(QMessageBox.Icon.Question, "Title", "Msg", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    yes_btn = box_zh.button(QMessageBox.StandardButton.Yes)
    no_btn = box_zh.button(QMessageBox.StandardButton.No)
    assert yes_btn is not None and "是" in yes_btn.text()
    assert no_btn is not None and "否" in no_btn.text()
    
    # Switch to en
    set_language("en")
    assert install_qt_translator(app, "en") is True
    box_en = QMessageBox(QMessageBox.Icon.Question, "Title", "Msg", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    yes_btn_en = box_en.button(QMessageBox.StandardButton.Yes)
    no_btn_en = box_en.button(QMessageBox.StandardButton.No)
    assert yes_btn_en is not None and "Yes" in yes_btn_en.text()
    assert no_btn_en is not None and "No" in no_btn_en.text()
    
    # Restore zh
    set_language("zh")
    install_qt_translator(app, "zh")


def test_stylesheet_contains_modern_tokens():
    from vidveya.ui.style import get_theme_stylesheet
    for theme in ("light", "dark"):
        qss = get_theme_stylesheet(theme)
        assert "QualityCard" in qss
        assert "HeroInput" in qss
        assert "SearchInput" in qss
        assert "InlineAction" in qss
