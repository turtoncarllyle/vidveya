from unittest.mock import Mock

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QTimer, Qt
from PySide6.QtWidgets import QListView, QMenu, QMessageBox

from fakes import WorkerFactory
from vidveya.formats import build_options
from vidveya.store import Store, timestamp
from vidveya.ui.window import MainWindow


@pytest.fixture
def make_window(qtbot, tmp_path, monkeypatch):
    windows = []
    monkeypatch.setattr('vidveya.ui.window.play_completion_sound', Mock())

    def create():
        store = Store(tmp_path / 'ui.db')
        store.set_setting('language', 'zh')
        store.set_setting('directory', str(tmp_path / '下载视频'))
        window = MainWindow(store, start_diagnostics=False)
        window.downloads.worker_factory = WorkerFactory()
        windows.append(window)
        return window

    yield create
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    for window in reversed(windows):
        window.request_exit()
        for attempt in list(window.downloads.active.values()):
            attempt.worker.finish()
        qtbot.waitUntil(lambda: not window.downloads.active and not window.workers)
        QCoreApplication.processEvents()
        store = window.store
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        store.close()


def start_fake_download(window, tmp_path):
    window.ready = True
    window.downloads.set_ready(True)
    window.downloads.enqueue(
        {'url': 'https://youtu.be/YE7VzlLtp-4', 'title': '中文视频'},
        {'key': '1920x1080:30:mp4', 'resolution': 1080, 'container': 'mp4',
         'width': 1920, 'height': 1080, 'fps': 30}, str(tmp_path))
    worker = window.downloads.worker_factory.workers[-1]
    worker.event_received.emit({'state': 'downloading', 'percent': 0})
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
    window.start_download()
    window.update_actions()
    assert window.download_button.isEnabled()
    assert len(window.downloads.active) == 1
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
    worker.event_received.emit({"state": "merging", "percent": None})
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


def test_exit_confirms_and_interrupts_active_download(make_window, tmp_path, monkeypatch, qtbot):
    window = make_window()
    window.store.set_setting('close_action', 'exit')
    window.store.set_setting('confirm_close', False)
    worker = start_fake_download(window, tmp_path)
    job_id = worker.request['job_id']
    window.show()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    assert not window.close()
    worker.cancel.assert_not_called()
    assert window.downloads.get(job_id)['state'] == 'downloading'
    assert not window.closing
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    assert not window.close()
    worker.cancel.assert_called_once()
    worker.wait.assert_not_called()
    assert window.isVisible() and window.closing
    worker.finish()
    qtbot.waitUntil(lambda: not window.isVisible())
    assert window.store.job(job_id)['state'] == 'interrupted'
    assert not window.downloads.active


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
    worker = start_fake_download(window, tmp_path)
    card = window.task_list.cards[worker.request['job_id']]
    worker.event_received.emit({'state': 'downloading', 'percent': 47.5, 'downloaded_bytes': 47.5 * 1024**2,
                                'total_bytes': 100 * 1024**2, 'speed': 3 * 1024**2, 'eta': 17})
    assert card.percent.text() == '47%'
    assert card.progress_bar.value() == 47
    assert card.progress_bar.maximum() == 100
    assert '47.5 MB / 100.0 MB' in card.details.text()
    assert '3.0 MB/s' in card.details.text()
    assert '剩余 0:17' in card.details.text()


@pytest.mark.parametrize("state, caption", [("downloading", "正在下载"), ("merging", "正在合并"), ("verifying", "正在校验")])
def test_unknown_percentage_displays_phase_without_fake_completion(make_window, tmp_path, state, caption):
    window = make_window()
    worker = start_fake_download(window, tmp_path)
    card = window.task_list.cards[worker.request['job_id']]
    worker.event_received.emit({'state': 'downloading', 'percent': 75})
    worker.event_received.emit({'state': state, 'percent': None, 'downloaded_bytes': 1024**2})
    assert caption in card.status.text()
    assert not card.percent.text()
    assert card.progress_bar.minimum() == card.progress_bar.maximum() == 0
    if state == 'downloading':
        assert '总大小待确定' in card.details.text()
        assert '1.0 MB' in card.details.text()


def test_progress_only_reaches_100_after_verified_result(make_window, tmp_path):
    window = make_window()
    worker = start_fake_download(window, tmp_path)
    card = window.task_list.cards[worker.request['job_id']]
    worker.event_received.emit({'state': 'downloading', 'percent': 100})
    assert card.percent.text() == '99%'
    worker.result_received.emit({'path': str(tmp_path / '有声视频.mp4'), 'verification': {'bytes': 1024}})
    assert card.percent.text() == '99%'
    worker.finish()
    assert card.percent.text() == '100%'
    assert card.progress_bar.value() == 100
    assert window.store.job(worker.request['job_id'])['state'] == 'completed'


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
    worker = start_fake_download(window, tmp_path)
    worker.event_received.emit({'state': 'downloading', 'percent': 50, 'speed': 2 * 1024**2})
    assert not window.sidebar_mini_task.isHidden()
    assert '1' in window.mini_title.text() and '2.0 MB/s' in window.mini_status.text()
    assert window.mini_progress.value() == 50
    worker.succeed({'path': str(tmp_path / '有声视频.mp4'), 'verification': {'bytes': 1024}})
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
        assert view.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        assert view.uniformItemSizes() is True


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
    active_id = worker.request['job_id']
    video = tmp_path / '已下载的视频.mp4'
    video.write_bytes(b'keep downloaded media')
    window.store.save_job({'id': 'finished', 'state': 'completed', 'created': timestamp(),
                           'title': '已完成', 'option': {}, 'result': {'path': str(video)}})
    window.refresh_history()
    active_row = next(i for i, job in enumerate(window.display_jobs) if job['id'] == active_id)
    window.history.selectRow(active_row)
    assert window.delete_history_button.isEnabled()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    getattr(window, action)()

    assert active_id in {job['id'] for job in window.store.jobs()}
    if action == 'clear_all_history':
        assert len(window.store.jobs()) == 1
        assert not window.clear_history_button.isEnabled()
        worker.cancel.assert_not_called()
        worker.event_received.emit({'state': 'merging', 'percent': None})
        assert window.store.job(active_id)['state'] == 'merging'
    else:
        worker.cancel.assert_called_once()
        assert window.store.job(active_id)['delete_requested']
    worker.succeed({'path': str(video), 'verification': {'bytes': video.stat().st_size}})
    if action == 'clear_all_history':
        assert window.store.job(active_id)['state'] == 'completed'
        assert window.task_list.cards[active_id].progress_bar.value() == 100
    else:
        assert window.store.job(active_id) is None
        assert active_id not in window.task_list.cards
    assert video.read_bytes() == b'keep downloaded media'


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


def test_active_history_context_menu_can_cancel_and_remove(make_window, tmp_path, monkeypatch):
    window = make_window()
    start_fake_download(window, tmp_path)
    window.refresh_history()
    monkeypatch.setattr(window.history, "itemAt", lambda pos: window.history.item(0, 0))
    enabled = []
    menu = QMenu(window)
    monkeypatch.setattr("vidveya.ui.window.QMenu", lambda parent: menu)
    monkeypatch.setattr(menu, "exec", lambda pos: enabled.append(menu.actions()[-1].isEnabled()))
    window.show_history_context_menu(QPoint(1, 1))
    assert enabled == [True]


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
    window.show_history()
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
    assert window.delete_history_button.isEnabled()

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
    from vidveya.ui.style import get_theme_stylesheet, LIGHT_THEME, DARK_THEME
    for tokens in (LIGHT_THEME, DARK_THEME):
        assert "warning_bg" in tokens
        assert "warning_text" in tokens
        assert "warning_border" in tokens

    for theme in ("light", "dark"):
        qss = get_theme_stylesheet(theme)
        assert "QualityCard" in qss
        assert "HeroInput" in qss
        assert "SearchInput" in qss
        assert "InlineAction" in qss
        assert "QFrame#SegmentedControl" in qss
        assert "QPushButton#SegmentBtn" in qss
        assert "QFrame#TaskCard" in qss
        assert "QProgressBar#TaskProgress" in qss
        assert "QFrame#SidebarMiniTask" in qss
        assert "QFrame#CompletionPopup" in qss
        assert "QLabel#RetryCountdown" in qss
        assert "QLabel#ProgressValue" in qss
        assert "QLabel#CodecBadge" in qss
        assert "QFrame#AddedBanner" in qss
        assert "QLabel#AddedBannerLabel" in qss
        assert "QLabel#ClipboardBadge" in qss
        assert "QLabel#ThumbnailPlaceholder" in qss


def test_new_modern_i18n_keys():
    from vidveya.i18n import t, set_language
    for lang in ("zh", "en"):
        set_language(lang)
        for key in ("hist_search_placeholder", "dl_recommended", "set_auto_saved", "dl_quality_title", "dl_audio_only", "dl_clipboard_detected", "dl_added_banner", "dl_view_transfers", "dl_continue", "dl_empty_guide"):
            assert t(key) != key


def test_download_page_hero_input_and_quality_chips(make_window, media_info):
    window = make_window()
    window.show()
    assert hasattr(window, "hero_box")
    assert window.hero_box.objectName() == "HeroInput"
    assert window.url_input.objectName() == "HeroUrlInput"
    assert hasattr(window, "clear_btn")
    assert not window.clear_btn.isVisible()

    window.url_input.setText("https://www.youtube.com/watch?v=YE7VzlLtp-4")
    assert window.clear_btn.isVisible()
    window.clear_btn.click()
    assert window.url_input.text() == ""
    assert not window.clear_btn.isVisible()

    window.ready = True
    info = {"video_id": media_info["id"], "url": "https://youtu.be/YE7VzlLtp-4", "title": "<中文标题>",
            "channel": "频道", "duration": 2, "thumbnail": None,
            "options": [option.to_dict() for option in build_options(media_info)]}
    window.show_video(info)
    assert hasattr(window, "quality_chips")
    assert len(window.quality_chips) == len(window.visible_options)
    assert len(window.quality_chips) > 0
    # Current selected row in table matches selected chip
    current_row = window.formats.currentRow()
    assert window.quality_chips[current_row].property("selected") == "true"
    # Clicking another chip selects that row in formats
    other_idx = (current_row + 1) % len(window.quality_chips)
    window.quality_chips[other_idx].clicked.emit(other_idx)
    assert window.formats.currentRow() == other_idx
    assert window.quality_chips[other_idx].property("selected") == "true"


def test_history_search_filter_and_clean_ui(make_window):
    window = make_window()
    window.show()
    assert hasattr(window, "search_input")
    assert window.search_input.objectName() == "SearchInput"
    assert hasattr(window, "history_actions_widget")
    assert not window.history_actions_widget.isVisible()

    window.store.save_job({"id": "job1", "state": "completed", "created": "2026-09-16T10:00:00",
                           "title": "Python Tutorial 2026", "option": {"resolution": 1080, "container": "mp4"}})
    window.store.save_job({"id": "job2", "state": "completed", "created": "2026-09-16T11:00:00",
                           "title": "Music Video HD", "option": {"resolution": 720, "container": "mp4"}})
    window.refresh_history()
    assert len(window.display_jobs) == 2

    window.show_history()
    window.search_input.setText("python")
    assert len(window.display_jobs) == 1
    assert window.display_jobs[0]["id"] == "job1"

    window.search_input.setText("nonexistentxyz")
    assert len(window.display_jobs) == 0

    window.search_input.clear()
    assert len(window.display_jobs) == 2


def test_settings_auto_save_on_changes(make_window):
    window = make_window()
    window.show()
    # Change close action
    window.close_action_input.setCurrentIndex(window.close_action_input.findData("exit"))
    assert window.store.get_setting("close_action") == "exit"
    assert "自动保存" in window.settings_notice.text()

    # Toggle confirm close
    window.close_prompt_input.setChecked(False)
    assert window.store.get_setting("confirm_close") is False

def test_paste_smart_auto_analyzes(make_window, monkeypatch):
    from PySide6.QtWidgets import QApplication

    window = make_window()
    window.ready = True
    window.show()

    # 1. Valid YouTube URL in clipboard triggers analyze
    analyzed_called = False

    def fake_analyze():
        nonlocal analyzed_called
        analyzed_called = True

    monkeypatch.setattr(window, "analyze", fake_analyze)
    monkeypatch.setattr(QApplication.clipboard(), "text", lambda: "https://www.youtube.com/watch?v=YE7VzlLtp-4")

    window.paste_smart()
    assert window.url_input.text() == "https://www.youtube.com/watch?v=YE7VzlLtp-4"
    assert analyzed_called is True

    # 2. Invalid URL in clipboard does not trigger analyze
    analyzed_called = False
    monkeypatch.setattr(QApplication.clipboard(), "text", lambda: "https://example.com/not_youtube")
    window.paste_smart()
    assert window.url_input.text() == "https://example.com/not_youtube"
    assert analyzed_called is False

    # 3. Non-ready state does not trigger analyze
    window.ready = False
    analyzed_called = False
    monkeypatch.setattr(QApplication.clipboard(), "text", lambda: "https://youtu.be/YE7VzlLtp-4")
    window.paste_smart()
    assert window.url_input.text() == "https://youtu.be/YE7VzlLtp-4"
    assert analyzed_called is False


def test_clipboard_sniffing(make_window, monkeypatch):
    from PySide6.QtWidgets import QApplication

    window = make_window()
    window.show()
    assert hasattr(window, "sniff_clipboard")

    # 1. Valid YouTube URL in clipboard automatically fills and shows badge
    valid_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    monkeypatch.setattr(QApplication.clipboard(), "text", lambda: valid_url)

    result = window.sniff_clipboard()
    assert result is True
    assert window.url_input.text() == valid_url
    assert hasattr(window, "clipboard_badge")
    assert window.clipboard_badge.isVisible()
    assert "已识别" in window.clipboard_badge.text()

    # 2. Second call with same text in clipboard returns False and does not re-fill
    result_again = window.sniff_clipboard()
    assert result_again is False

    # 3. Invalid URL in clipboard returns False and does not alter existing valid text
    monkeypatch.setattr(QApplication.clipboard(), "text", lambda: "https://google.com")
    result_invalid = window.sniff_clipboard()
    assert result_invalid is False
    assert window.url_input.text() == valid_url


def test_download_in_place_feedback_banner_and_empty_state(make_window, media_info):
    window = make_window()
    window.ready = True
    window.show()

    # 1. Initial empty state shows modern guide and hides video card
    assert hasattr(window, "empty_placeholder")
    assert window.empty_placeholder.isVisible()
    assert window.video_card.isHidden()
    assert hasattr(window, "added_actions")
    assert window.added_actions.isHidden()
    assert "复制 YouTube 视频链接" in window.empty_guide_title.text()

    # 2. Loading video switches from empty state to video card & chips
    info = {
        "video_id": media_info["id"],
        "url": "https://youtu.be/YE7VzlLtp-4",
        "title": "<中文标题>",
        "channel": "频道",
        "duration": 2,
        "thumbnail": None,
        "options": [option.to_dict() for option in build_options(media_info)],
    }
    window.show_video(info)
    assert window.empty_placeholder.isHidden()
    assert window.video_card.isVisible()
    assert window.chips_widget.isVisible()

    # 3. Starting download displays added_actions banner
    window.start_download()
    assert window.added_actions.isVisible()
    assert hasattr(window, "view_transfers_btn")
    assert hasattr(window, "continue_add_btn")

    # 4. Clicking 'View Transfers' switches to page index 1
    window.view_transfers_btn.click()
    assert window.pages.currentIndex() == 1

    # Switch back to download page (0)
    window.pages.setCurrentIndex(0)
    # 5. Clicking 'Continue Add' resets input and hides added_actions banner
    window.continue_add_btn.click()
    assert window.added_actions.isHidden()
    assert window.url_input.text() == ""
    assert window.empty_placeholder.isVisible()
    assert window.video_card.isHidden()


def test_clipboard_sniffing_event_triggers(make_window, monkeypatch):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    window = make_window()
    window.show()

    sniff_calls = 0
    def fake_sniff():
        nonlocal sniff_calls
        sniff_calls += 1
        return True

    monkeypatch.setattr(window, 'sniff_clipboard', fake_sniff)

    # 1. ActivationChange when active triggers sniff_clipboard
    monkeypatch.setattr(window, 'isActiveWindow', lambda: True)
    window.changeEvent(QEvent(QEvent.Type.ActivationChange))
    assert sniff_calls == 1

    # 2. FocusIn on url_input triggers sniff_clipboard
    focus_event = QEvent(QEvent.Type.FocusIn)
    window.eventFilter(window.url_input, focus_event)
    assert sniff_calls == 2

    # 3. Ctrl+V key press on url_input with valid YouTube URL triggers paste_smart
    from PySide6.QtWidgets import QApplication
    monkeypatch.setattr(QApplication.clipboard(), 'text', lambda: 'https://www.youtube.com/watch?v=YE7VzlLtp-4')
    paste_calls = 0
    def fake_paste():
        nonlocal paste_calls
        paste_calls += 1

    monkeypatch.setattr(window, 'paste_smart', fake_paste)
    paste_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    handled = window.eventFilter(window.url_input, paste_event)
    assert handled is True
    assert paste_calls == 1


def test_clipboard_sniffing_dismissal_and_scope_guard(make_window, monkeypatch):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication

    window = make_window()
    window.show()

    valid_url = "https://www.youtube.com/watch?v=YE7VzlLtp-4"
    valid_url_2 = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    monkeypatch.setattr(QApplication.clipboard(), "text", lambda: valid_url)

    # 1. Initially sniff fills the URL
    assert window.sniff_clipboard() is True
    assert window.url_input.text() == valid_url
    assert window.clipboard_badge.isVisible()

    # 2. Editing text hides the badge
    window.url_input.setText(valid_url + "edit")
    assert window.clipboard_badge.isHidden()

    # 3. User clicks clear_btn: dismissed clipboard prevents revival on focus
    window.clear_btn.click()
    assert window.url_input.text() == ""
    # Simulating FocusIn
    focus_in = QEvent(QEvent.Type.FocusIn)
    window.eventFilter(window.url_input, focus_in)
    assert window.url_input.text() == ""  # Did NOT revive!
    assert window.sniff_clipboard() is False

    # 4. When clipboard content changes to a new URL, sniffing works again
    monkeypatch.setattr(QApplication.clipboard(), "text", lambda: valid_url_2)
    assert window.sniff_clipboard() is True
    assert window.url_input.text() == valid_url_2

    # 5. reset_for_next() also dismisses current clipboard
    window.reset_for_next()
    assert window.url_input.text() == ""
    window.eventFilter(window.url_input, focus_in)
    assert window.url_input.text() == ""  # Did NOT revive!

    # 6. Cross-page scope guard: not on page 0 -> returns False
    monkeypatch.setattr(QApplication.clipboard(), "text", lambda: valid_url)
    window.pages.setCurrentIndex(1)
    assert window.sniff_clipboard() is False
    assert window.url_input.text() == ""

    # 7. State split guard: on page 0, but video is already loaded or downloading
    window.pages.setCurrentIndex(0)
    window.video = {"title": "Existing"}
    assert window.sniff_clipboard() is False
    assert window.url_input.text() == ""
    window.video = None

    # 8. KeyPress paste fallback when clipboard is invalid
    monkeypatch.setattr(QApplication.clipboard(), "text", lambda: "plain search text")
    paste_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    handled = window.eventFilter(window.url_input, paste_event)
    assert handled is False  # falls back to native QLineEdit paste


def add_workbench_task(window, number=0, resolution=1080):
    window.ready = True
    info = {'title': f'中文视频 {number}', 'url': f'https://youtu.be/YE7VzlLtp-{number}'}
    option = {'key': f'{resolution}:mp4', 'resolution': resolution, 'container': 'mp4',
              'width': 1920, 'height': 1080, 'fps': 30}
    window.start_job(info, option)
    return next(job for job in window.downloads.jobs.values()
                if job['url'].endswith(f'YE7VzlLtp-{number}') and job['option']['key'] == option['key'])


def test_workbench_keeps_selected_tab_during_progress_and_duplicate_focus(make_window):
    window = make_window()
    job = add_workbench_task(window)
    page = window.transfers_page
    window.show_history()
    window.history.selectRow(0)
    window.show_tasks()
    assert page.content_stack.currentIndex() == 0
    window.downloads.worker_factory.workers[0].event_received.emit({'state': 'verifying', 'percent': None})
    assert page.content_stack.currentIndex() == 0
    window.show_history()
    window.search_input.setText('unmatched')
    window.start_job(job, job['option'])
    assert len(window.downloads.jobs) == 1
    assert page.content_stack.currentIndex() == 0
    assert window.task_list.selected_id == job['id']
    assert window.task_list.visible_ids == [job['id']]
    assert not window.search_input.text()
    window.view_transfers_btn.click()
    assert page.content_stack.currentIndex() == 0


def test_five_ui_tasks_have_three_workers_and_independent_slots(make_window):
    window = make_window()
    jobs = [add_workbench_task(window, i) for i in range(5)]
    factory = window.downloads.worker_factory
    assert len(factory.workers) == 3
    assert [job['state'] for job in jobs] == ['starting'] * 3 + ['queued'] * 2
    factory.workers[1].fail(retryable=False)
    assert jobs[1]['state'] == 'failed' and jobs[3]['state'] == 'starting'
    assert jobs[4]['state'] == 'queued' and len(factory.workers) == 4
    window.task_list.cards[jobs[0]['id']].cancel_button.click()
    factory.workers[0].cancel.assert_called_once()
    factory.workers[2].cancel.assert_not_called()
    factory.workers[0].finish()
    assert jobs[4]['state'] == 'starting' and len(factory.workers) == 5


def test_workbench_pause_and_resume_queue_buttons_dispatch_real_manager(make_window):
    window = make_window()
    jobs = [add_workbench_task(window, i) for i in range(5)]
    page = window.transfers_page
    factory = window.downloads.worker_factory
    page.pause_all_btn.click()
    assert window.downloads.paused and not page.resume_all_btn.isHidden()
    assert page.pause_all_btn.isHidden() and not page.queue_notice.isHidden()
    factory.workers[0].succeed({'path': 'verified.mp4', 'verification': {'bytes': 10}})
    assert len(factory.workers) == 3 and jobs[3]['state'] == 'queued'
    for worker in factory.workers:
        worker.cancel.assert_not_called()
    page.resume_all_btn.click()
    assert not window.downloads.paused
    assert len(factory.workers) == 4 and jobs[3]['state'] == 'starting'
    assert page.resume_all_btn.isHidden() and page.queue_notice.isHidden()


def test_failed_card_stays_visible_and_retry_focuses_new_task(make_window):
    window = make_window()
    job = add_workbench_task(window)
    window.show()
    window.show_tasks()
    window.downloads.worker_factory.workers[0].fail(retryable=False)
    page = window.transfers_page
    assert page.content_stack.currentIndex() == 0 and page.task_scroll.isVisible()
    card = window.task_list.cards[job['id']]
    assert card.isVisible() and card.retry_button.isVisible()
    card.retry_button.click()
    assert len(window.downloads.jobs) == 2
    assert window.task_list.selected_id != job['id']
    assert window.downloads.get(window.task_list.selected_id)['attempts'] == 1
    assert page.content_stack.currentIndex() == 0


def test_filtered_task_keyboard_selection_ignores_hidden_cards(make_window):
    window = make_window()
    jobs = [add_workbench_task(window, i) for i in range(3)]
    window.show_tasks()
    window.search_input.setText('视频 2')
    assert window.task_list.visible_ids == [jobs[2]['id']]
    assert window.task_list.selected_id == jobs[2]['id']
    window.task_list.move_selection(-1)
    assert window.task_list.selected_id == jobs[2]['id']
    window.search_input.setText('unmatched')
    assert window.task_list.visible_ids == [] and window.task_list.selected_id is None
    assert all(frame.isHidden() for frame, *_ in window.task_list.groups)


def test_restart_shows_continue_queue_without_automatic_download(make_window, monkeypatch):
    first = make_window()
    first.downloads.pause_queue()
    job = add_workbench_task(first)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    first.request_exit()
    reopened = make_window()
    reopened.components_checked({'QA': {'ok': True, 'version': 'test component'}})
    assert reopened.downloads.paused and not reopened.downloads.active
    assert not reopened.transfers_page.resume_all_btn.isHidden()
    reopened.transfers_page.resume_all_btn.click()
    assert reopened.downloads.get(job['id'])['state'] == 'starting'


def test_history_delete_shortcut_waits_for_worker_exit(make_window, qtbot, monkeypatch):
    window = make_window()
    job = add_workbench_task(window)
    window.show()
    window.show_history()
    window.history.selectRow(0)
    window.activateWindow()
    qtbot.waitUntil(window.isActiveWindow)
    window.history.setFocus()
    qtbot.waitUntil(window.history.hasFocus)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    assert not window.history_delete_shortcut.autoRepeat()
    qtbot.keyClick(window.history, Qt.Key.Key_Delete)
    assert window.store.job(job['id'])['delete_requested']
    worker = window.downloads.worker_factory.workers[0]
    worker.cancel.assert_called_once()
    worker.finish()
    assert window.store.job(job['id']) is None
    assert job['id'] not in window.task_list.cards and window.history.rowCount() == 0


@pytest.mark.parametrize('control', ['url_input', 'search_input'])
def test_delete_in_text_input_never_removes_history(make_window, qtbot, monkeypatch, control):
    window = make_window()
    job = add_workbench_task(window)
    window.show()
    window.show_history()
    window.history.selectRow(0)
    if control == 'url_input':
        window.show_page(window.NEW_PAGE)
    widget = getattr(window, control)
    widget.setText('中文视频')
    widget.setFocus()
    widget.setCursorPosition(0)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: pytest.fail('输入框 Delete 不应删除任务'))
    qtbot.keyClick(widget, Qt.Key.Key_Delete)
    assert widget.text() == '文视频'
    assert window.store.job(job['id']) is not None
    assert not window.downloads.get(job['id'])['delete_requested']


def test_task_card_has_no_delete_shortcut(make_window, qtbot, monkeypatch):
    window = make_window()
    job = add_workbench_task(window)
    window.show()
    window.show_tasks()
    window.task_list.select(job['id'], focus=True)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: pytest.fail('任务卡片不应绑定 Delete'))
    qtbot.keyClick(window.task_list.cards[job['id']], Qt.Key.Key_Delete)
    assert window.store.job(job['id']) and not job['delete_requested']


def test_new_pasted_url_discards_previous_analysis_then_parses_latest(make_window, media_info, monkeypatch):
    from PySide6.QtWidgets import QApplication
    window = make_window()
    window.ready = True
    factory = WorkerFactory()
    monkeypatch.setattr('vidveya.ui.window.WorkerThread', factory)
    original = 'https://www.youtube.com/watch?v=YE7VzlLtp-4'
    latest = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
    window.url_input.setText(original)
    window.analyze()
    monkeypatch.setattr(QApplication.clipboard(), 'text', lambda: latest)
    window.paste_smart()
    info = {'title': '旧视频', 'channel': '频道', 'duration': 2, 'url': original,
            'options': [option.to_dict() for option in build_options(media_info)]}
    factory.workers[0].result_received.emit(info)
    assert window.video is None and not window.download_button.isEnabled()
    factory.workers[0].finish()
    assert len(factory.workers) == 2 and factory.workers[1].request['url'] == latest
    factory.workers[1].result_received.emit(info | {'url': latest, 'title': '新视频'})
    factory.workers[1].finish()
    assert window.video['title'] == '新视频' and window.download_button.isEnabled()


def test_exit_waits_for_analysis_and_download_callbacks(make_window, monkeypatch, qtbot):
    window = make_window()
    job = add_workbench_task(window)
    factory = WorkerFactory()
    monkeypatch.setattr('vidveya.ui.window.WorkerThread', factory)
    window.url_input.setText('https://youtu.be/YE7VzlLtp-4')
    window.analyze()
    window.show()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    assert not window.request_exit()
    factory.workers[0].cancel.assert_called_once()
    factory.workers[0].wait.assert_not_called()
    factory.workers[0].finish()
    assert window.isVisible()
    window.downloads.worker_factory.workers[0].finish()
    qtbot.waitUntil(lambda: not window.isVisible())
    assert window.store.job(job['id'])['state'] == 'interrupted'
    assert not window.workers and not window.downloads.active


def test_completion_notification_defaults_off_and_sound_waits_for_success(make_window, monkeypatch):
    window = make_window()
    job = add_workbench_task(window)
    sound = Mock()
    monkeypatch.setattr('vidveya.ui.window.play_completion_sound', sound)
    worker = window.downloads.worker_factory.workers[0]
    assert not window.completion_notifier.enabled
    worker.event_received.emit({'state': 'verifying', 'percent': None})
    sound.assert_not_called()
    worker.succeed({'path': 'verified.mp4', 'verification': {'bytes': 10}})
    assert window.store.job(job['id'])['state'] == 'completed'
    sound.assert_called_once()
    assert window.completion_notifier.pending == [] and window.completion_notifier.popup is None

