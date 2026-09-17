import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QWidget

from vidveya.ui.notifications import CompletionNotifier
from vidveya.ui.style import get_theme_stylesheet


@pytest.fixture
def notifier(qapp):
    owner = QWidget()
    notifications = CompletionNotifier(owner, enabled=True)
    yield notifications, owner
    notifications.shutdown()
    owner.close()
    owner.deleteLater()


def test_notification_batches_titles_and_fits_above_taskbar(notifier, qtbot):
    notifications, owner = notifier
    owner.showMinimized()
    option = {"resolution": 1080, "container": "mp4"}
    notifications.notify("<中文视频>", option)
    notifications.notify("Big Buck Bunny", option)
    assert notifications.popup is None and notifications.timer.isActive()
    notifications.flush()
    popup = notifications.popup
    qtbot.waitUntil(popup.isVisible)
    assert owner.isMinimized()
    assert "2 个视频下载完成" in popup.heading.text()
    assert [row.title.text() for row in popup.rows] == ["<中文视频>", "Big Buck Bunny"]
    assert all(row.quality.text() == "1080P · MP4" for row in popup.rows)
    assert all(row.title.textFormat() == Qt.TextFormat.PlainText for row in popup.rows)
    assert popup.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    assert popup.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    area = owner.screen().availableGeometry()
    assert area.contains(popup.geometry())
    assert 10 <= area.right() - popup.geometry().right() <= 30
    assert 10 <= area.bottom() - popup.geometry().bottom() <= 30
    with qtbot.waitSignal(notifications.activated):
        popup.open_button.click()
    assert not popup.isVisible()


def test_disable_or_shutdown_cancels_pending_notification(notifier, qtbot):
    notifications, _ = notifier
    option = {"resolution": 720, "container": "mp4"}
    notifications.notify("First", option)
    notifications.set_enabled(False)
    assert not notifications.timer.isActive() and notifications.pending == []
    notifications.flush()
    assert notifications.popup is None
    notifications.set_enabled(True)
    notifications.notify("Second", option)
    notifications.flush()
    assert notifications.popup.isVisible()
    notifications.set_enabled(False)
    assert not notifications.popup.isVisible()
    notifications.set_enabled(True)
    notifications.notify("Third", option)
    notifications.shutdown()
    assert notifications.popup is None and not notifications.timer.isActive() and notifications.pending == []


def test_notification_limits_long_batch_text_and_dismiss_does_not_activate(notifier, qtbot):
    notifications, _ = notifier
    for index in range(5):
        notifications.notify(f"视频 {index} " + "长标题" * 100, {"resolution": 2160, "container": "webm"})
    notifications.flush()
    popup = notifications.popup
    assert "5 个视频" in popup.heading.text()
    assert "还有 2 个视频" in popup.more_label.text()
    assert len(popup.rows) == 3
    assert all(len(row.title.text()) <= 65 for row in popup.rows)
    with qtbot.assertNotEmitted(notifications.activated):
        popup.dismiss_button.click()
    assert not popup.isVisible()


def test_each_completion_opens_its_own_file_and_folder(notifier, tmp_path, qtbot):
    notifications, _ = notifier
    first = str(tmp_path / "第一个视频.mp4")
    second = str(tmp_path / "第二个视频.mp4")
    option = {"resolution": 1080, "container": "mp4"}
    notifications.notify("第一个视频", option, first)
    notifications.notify("第二个视频", option, second)
    notifications.flush()
    popup = notifications.popup
    with qtbot.waitSignal(notifications.open_file_requested, check_params_cb=lambda path: path == first):
        qtbot.mouseClick(popup.rows[0].file_button, Qt.MouseButton.LeftButton)
    assert not popup.isVisible()
    popup.show()
    with qtbot.waitSignal(notifications.open_folder_requested, check_params_cb=lambda path: path == second):
        qtbot.mouseClick(popup.rows[1].folder_button, Qt.MouseButton.LeftButton)
    assert not popup.isVisible()


@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_notification_heading_remains_readable_on_rendered_background(notifier, qtbot, theme):
    notifications, owner = notifier
    owner.setStyleSheet(get_theme_stylesheet(theme))
    notifications.notify('画面与声音校验成功', {'resolution': 1080, 'container': 'mp4'})
    notifications.flush()
    popup = notifications.popup
    qtbot.waitUntil(popup.isVisible)
    background = popup.grab().toImage().pixelColor(8, 30)
    foreground = popup.heading.palette().color(QPalette.ColorRole.WindowText)

    def luminance(color):
        channels = [value / 255 for value in (color.red(), color.green(), color.blue())]
        linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
                  for value in channels]
        return sum(weight * value for weight, value in zip((0.2126, 0.7152, 0.0722), linear))

    dark, light = sorted((luminance(background), luminance(foreground)))
    assert (light + 0.05) / (dark + 0.05) >= 4.5
