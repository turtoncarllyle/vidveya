from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ..i18n import t


def play_completion_sound() -> None:
    """Play the Windows notification sound without delaying download completion."""
    try:
        import winsound

        winsound.PlaySound(
            "SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        )
    except (ImportError, RuntimeError, OSError):
        # A missing sound device or disabled system sound must not fail a download.
        pass


class CompletionItem(QFrame):
    open_file_requested = Signal(str)
    open_folder_requested = Signal(str)

    def __init__(self, title, option, path):
        super().__init__()
        self.setObjectName("NotificationItem")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        full_title = " ".join(title.split())
        self.title = QLabel(full_title[:64] + "…" if len(full_title) > 64 else full_title)
        self.title.setToolTip(full_title)
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        self.quality = QLabel(f"{option.get('resolution', '')}P · {option.get('container', '').upper()}")
        self.quality.setTextFormat(Qt.TextFormat.PlainText)
        self.quality.setObjectName("Muted")
        layout.addWidget(self.quality)
        actions = QHBoxLayout()
        self.file_button = QPushButton(t("notification_open_file"))
        self.folder_button = QPushButton(t("dl_btn_open_dir"))
        for button in (self.file_button, self.folder_button):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setEnabled(bool(path))
            button.setToolTip(path)
            actions.addWidget(button)
        actions.addStretch()
        self.file_button.clicked.connect(lambda: self.open_file_requested.emit(path))
        self.folder_button.clicked.connect(lambda: self.open_folder_requested.emit(path))
        layout.addLayout(actions)


class CompletionPopup(QFrame):
    """A desktop notification that stays visible when the main window is minimized."""
    activated = Signal()
    open_file_requested = Signal(str)
    open_folder_requested = Signal(str)

    def __init__(self):
        # A separate top-level window avoids inheriting the owner's minimized state.
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setObjectName("CompletionPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.setAccessibleName(t("notification_complete"))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        header = QHBoxLayout()
        self.heading = QLabel()
        self.heading.setObjectName("Subheading")
        self.heading.setTextFormat(Qt.TextFormat.PlainText)
        header.addWidget(self.heading, 1)
        self.dismiss_button = QPushButton("×")
        self.dismiss_button.setObjectName("NotificationClose")
        self.dismiss_button.setAccessibleName(t("notification_dismiss"))
        self.dismiss_button.setFixedSize(28, 28)
        self.dismiss_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.dismiss_button.clicked.connect(self.hide)
        header.addWidget(self.dismiss_button)
        layout.addLayout(header)
        self.items_layout = QVBoxLayout()
        self.items_layout.setSpacing(16)
        self.rows = []
        layout.addLayout(self.items_layout)
        self.more_label = QLabel()
        self.more_label.setObjectName("Muted")
        self.more_label.setTextFormat(Qt.TextFormat.PlainText)
        self.more_label.setWordWrap(True)
        layout.addWidget(self.more_label)
        self.open_button = QPushButton(t("task_view"))
        self.open_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.open_button.clicked.connect(self.open_tasks)
        layout.addWidget(self.open_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.dismiss_timer = QTimer(self)
        self.dismiss_timer.setSingleShot(True)
        self.dismiss_timer.timeout.connect(self.hide)

    def show_completion(self, entries, screen):
        count = len(entries)
        heading = t("notification_complete") if count == 1 else t("notification_multiple").format(count=count)
        self.heading.setText(heading)
        for row in self.rows:
            self.items_layout.removeWidget(row)
            row.hide()
            row.deleteLater()
        self.rows = []
        for title, option, path in entries[:3]:
            row = CompletionItem(title, option, path)
            row.open_file_requested.connect(self.open_file)
            row.open_folder_requested.connect(self.open_folder)
            self.items_layout.addWidget(row)
            self.rows.append(row)
        self.more_label.setText(t("notification_more").format(count=count - 3) if count > 3 else "")
        self.more_label.setVisible(count > 3)
        available = screen.availableGeometry()
        self.setFixedWidth(min(400, max(240, available.width() - 32)))
        self.adjustSize()
        self.move(available.right() - self.width() - 19,
                  max(available.top() + 16, available.bottom() - self.height() - 19))
        self.show()
        self.dismiss_timer.start(8000)

    def open_tasks(self):
        self.hide()
        self.activated.emit()

    def open_file(self, path):
        self.hide()
        self.open_file_requested.emit(path)

    def open_folder(self, path):
        self.hide()
        self.open_folder_requested.emit(path)

    def enterEvent(self, event):
        self.dismiss_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.dismiss_timer.start(4000)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_tasks()
            event.accept()
            return
        super().mousePressEvent(event)


class CompletionNotifier(QObject):
    activated = Signal()
    open_file_requested = Signal(str)
    open_folder_requested = Signal(str)

    def __init__(self, owner, enabled=False):
        super().__init__(owner)
        self.owner = owner
        self.enabled = enabled
        self.pending = []
        self.popup = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.flush)

    def notify(self, title, option, path=""):
        if not self.enabled:
            return
        self.pending.append((title, dict(option), path))
        if not self.timer.isActive():
            self.timer.start(1000)

    def flush(self):
        self.timer.stop()
        entries, self.pending = self.pending, []
        if not self.enabled or not entries or not self.owner.screen():
            return
        if self.popup is None:
            self.popup = CompletionPopup()
            self.popup.activated.connect(self.activated.emit)
            self.popup.open_file_requested.connect(self.open_file_requested.emit)
            self.popup.open_folder_requested.connect(self.open_folder_requested.emit)
        self.popup.setStyleSheet(self.owner.styleSheet())
        self.popup.show_completion(entries, self.owner.screen())

    def set_enabled(self, enabled):
        self.enabled = enabled
        if not enabled:
            self.timer.stop()
            self.pending.clear()
            if self.popup:
                self.popup.hide()

    def shutdown(self):
        self.set_enabled(False)
        if self.popup:
            self.popup.deleteLater()
            self.popup = None
