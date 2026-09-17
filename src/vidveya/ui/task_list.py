import math

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from ..i18n import t
from ..models import ACTIVE_STATES, RUNNING_STATES, STATE_LABELS, WAITING_STATES
from .formatting import duration_text, size_text


def text_label(text="", role="Muted"):
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setObjectName(role)
    label.setWordWrap(True)
    return label


class TaskCard(QFrame):
    selected = Signal(str)
    move_selection = Signal(int)
    cancel_requested = Signal(str)
    retry_requested = Signal(str)
    play_requested = Signal(str)
    reveal_requested = Signal(str)

    def __init__(self, job_id, parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self.setObjectName("TaskCard")
        self.setProperty("selected", "false")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        # 1. 顶部视频主标题（全宽展示，不受按钮挤压）
        self.title = text_label(role="Subheading")
        layout.addWidget(self.title)

        # 2. 规格与标签
        self.format_label = text_label()
        self.format_label.setObjectName("CodecBadge")
        layout.addWidget(self.format_label)

        # 3. 状态与进度百分比
        state_row = QHBoxLayout()
        self.status = text_label(role="Status")
        self.percent = text_label(role="ProgressValue")
        self.percent.setAlignment(Qt.AlignmentFlag.AlignRight)
        state_row.addWidget(self.status, 1)
        state_row.addWidget(self.percent)
        layout.addLayout(state_row)

        # 4. 细进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("TaskProgress")
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        # 5. 醒目自适应重试倒计时横幅与错误提示
        self.retry_banner = QLabel()
        self.retry_banner.setObjectName("RetryCountdown")
        self.retry_banner.setWordWrap(True)
        self.retry_banner.hide()
        layout.addWidget(self.retry_banner)

        self.error = text_label(role="Notice")
        self.error.hide()
        layout.addWidget(self.error)

        # 6. 底部信息与操作按钮组（左侧详情，右侧紧凑操作按钮）
        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 2, 0, 0)
        footer_row.setSpacing(10)
        self.details = text_label()
        footer_row.addWidget(self.details, 1)

        self.cancel_button = self._button("dl_btn_cancel", self.cancel_requested)
        self.retry_button = self._button("hist_btn_retry", self.retry_requested)
        self.play_button = self._button("dl_btn_play", self.play_requested)
        self.reveal_button = self._button("dl_btn_open_dir", self.reveal_requested)
        for control in (self.cancel_button, self.retry_button, self.play_button, self.reveal_button):
            control.setObjectName("InlineAction")
            footer_row.addWidget(control)
        layout.addLayout(footer_row)

    def _button(self, key, signal):
        button = QPushButton(t(key))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.installEventFilter(self)
        button.clicked.connect(lambda: signal.emit(self.job_id))
        return button

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.FocusIn:
            self.selected.emit(self.job_id)
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self.selected.emit(self.job_id)
        super().mousePressEvent(event)

    def focusInEvent(self, event):
        self.selected.emit(self.job_id)
        super().focusInEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.move_selection.emit(-1 if event.key() == Qt.Key.Key_Up else 1)
            event.accept()
            return
        super().keyPressEvent(event)

    def render(self, job, progress, *, paused, now, position):
        option, state = job["option"], job["state"]
        self.title.setText(job["title"])
        self.title.setToolTip(job["title"])
        self.setAccessibleName(job["title"])
        fields = [f"{option.get('resolution', '')}P"]
        if option.get("width") and option.get("height"):
            fields.append(f"{option['width']}×{option['height']}")
        if option.get("fps"):
            fields.append(f"{option['fps']:g} FPS")
        fields.append(option.get("container", "").upper())
        self.format_label.setText(" · ".join(fields))
        status = t(f"state_{state}", STATE_LABELS.get(state, state))
        if job.get("delete_requested"):
            status = t("task_removing")
        elif job.get("cancel_requested") and state in RUNNING_STATES:
            status = t("dl_btn_cancelling")
        elif state == "retry_wait":
            status = t("task_retry_wait").format(number=job.get("attempts", 1), limit=job.get("retry_limit", 3),
                                                 seconds=max(0, math.ceil((job.get("next_retry_at") or now) - now)))
        elif state == "queued":
            status = t("task_queue_position").format(position=position)
        elif state == "failed":
            status += " · " + t("task_retried").format(count=max(0, job.get("attempts", 1) - 1))
        if paused and state in WAITING_STATES:
            status = t("task_resume_required") + " · " + status
        self.status.setText(status)
        running = state in RUNNING_STATES
        self.progress_bar.setVisible(running or state == "completed")
        percent = 100 if state == "completed" else progress.get("percent")
        if running and percent is None:
            self.progress_bar.setRange(0, 0)
            self.percent.clear()
        elif percent is not None and (running or state == "completed"):
            value = 100 if state == "completed" else min(99, max(0, int(percent)))
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(value)
            self.percent.setText(f"{value}%")
        else:
            self.percent.clear()
        details = ""
        if state == "downloading":
            details = t("dl_downloaded") + " " + size_text(progress.get("downloaded_bytes", 0))
            details += " / " + size_text(progress.get("total_bytes"))
            if progress.get("speed"):
                details += " · " + size_text(progress["speed"]) + "/s"
            if progress.get("eta") is not None:
                details += " · " + t("dl_eta") + " " + duration_text(progress["eta"])
        elif state == "completed":
            details = size_text(job.get("result", {}).get("verification", {}).get("bytes"))
        elif running:
            details = t({"starting": "dl_progress_refreshing", "merging": "dl_progress_merging_meta",
                         "verifying": "dl_progress_verifying_meta"}.get(state, "dl_progress_refreshing"))
        self.details.setText(details)
        self.details.setVisible(bool(details))
        if state == "retry_wait":
            seconds = max(0, math.ceil((job.get("next_retry_at") or now) - now))
            err_text = job.get("error", "")
            banner_text = f"⚠️ {t('task_retry_wait').format(number=job['attempts'], limit=job['retry_limit'], seconds=seconds)}"
            if err_text:
                banner_text += f"\n   {err_text}"
            self.retry_banner.setText(banner_text)
            self.retry_banner.show()
            self.error.hide()
        else:
            self.retry_banner.hide()
            self.error.setText(job.get("error", ""))
            self.error.setVisible(bool(job.get("error")) and state in {"failed", "interrupted"})
        self.cancel_button.setVisible(state in ACTIVE_STATES)
        self.cancel_button.setText(t("task_cancel_queue") if state in WAITING_STATES else t("dl_btn_cancel"))
        self.cancel_button.setEnabled(not job.get("cancel_requested") and not job.get("delete_requested"))
        self.retry_button.setVisible(state in {"failed", "cancelled", "interrupted"})
        has_file = state == "completed" and bool(job.get("result", {}).get("path"))
        self.play_button.setVisible(has_file)
        self.reveal_button.setVisible(has_file)


class TaskList(QWidget):
    cancel_requested = Signal(str)
    retry_requested = Signal(str)
    play_requested = Signal(str)
    reveal_requested = Signal(str)

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.cards = {}
        self.selected_id = None
        self.visible_ids = []
        self._signature = None
        self._selecting = False
        self.filter_keyword = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.groups = []
        for key in ("task_group_running", "task_group_waiting", "task_group_finished"):
            frame = QWidget()
            column = QVBoxLayout(frame)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(10)
            heading = text_label(t(key), "Section")
            column.addWidget(heading)
            layout.addWidget(frame)
            self.groups.append((frame, column, heading, key))
        self.empty = text_label(t("task_empty"))
        layout.addWidget(self.empty)
        manager.job_changed.connect(self.refresh)
        manager.job_removed.connect(self.refresh)
        manager.summary_changed.connect(self.refresh)
        self.refresh()

    def set_filter(self, keyword: str):
        self.filter_keyword = (keyword or "").strip().lower()
        self._apply_filter()

    def _apply_filter(self):
        kw = getattr(self, "filter_keyword", "")
        visible_any = False
        for identity, card in self.cards.items():
            job = self.manager.get(identity)
            if not job:
                continue
            matches = not kw or kw in job.get("title", "").lower()
            card.setVisible(matches)
            if matches:
                visible_any = True
        self.empty.setVisible(not visible_any)

    def select(self, job_id, focus=False):
        if self._selecting or job_id not in self.cards:
            return
        self._selecting = True
        try:
            previous = self.selected_id
            self.selected_id = job_id
            for identity in (previous, job_id):
                card = self.cards.get(identity)
                if card:
                    card.setProperty("selected", "true" if identity == job_id else "false")
                    card.style().unpolish(card)
                    card.style().polish(card)
                    card.update()
            if focus:
                self.cards[job_id].setFocus()
        finally:
            self._selecting = False

    def move_selection(self, delta):
        if self.selected_id in self.visible_ids:
            index = max(0, min(len(self.visible_ids) - 1, self.visible_ids.index(self.selected_id) + delta))
            self.select(self.visible_ids[index], focus=True)

    def refresh(self, *_):
        jobs = list(self.manager.jobs.values())
        positions = {identity: index + 1 for index, identity in enumerate(self.manager.queue)}
        groups = [[job for job in jobs if job["state"] in RUNNING_STATES],
                  sorted((job for job in jobs if job["state"] in WAITING_STATES),
                         key=lambda job: (job["state"] == "retry_wait",
                                           positions.get(job["id"], job.get("next_retry_at") or 0))),
                  sorted((job for job in jobs if job["state"] not in ACTIVE_STATES),
                         key=lambda job: job.get("finished_at", 0), reverse=True)[:3]]
        signature = tuple(tuple(job["id"] for job in group) for group in groups)
        ids = [identity for group in signature for identity in group]
        for identity in list(self.cards):
            if identity not in ids:
                card = self.cards.pop(identity)
                card.hide()
                card.deleteLater()
        for index, group in enumerate(groups):
            frame, column, heading, key = self.groups[index]
            frame.setVisible(bool(group))
            heading.setText(t(key) + f" ({len(group)})")
            for job in group:
                identity = job["id"]
                if identity not in self.cards:
                    card = TaskCard(identity)
                    card.selected.connect(self.select)
                    card.move_selection.connect(self.move_selection)
                    for name in ("cancel_requested", "retry_requested", "play_requested", "reveal_requested"):
                        getattr(card, name).connect(getattr(self, name).emit)
                    self.cards[identity] = card
                card = self.cards[identity]
                if signature != self._signature:
                    column.addWidget(card)
                    card.show()
                position = positions.get(identity, 1)
                card.render(job, self.manager.progress.get(identity, {}), paused=self.manager.paused,
                            now=self.manager.clock(), position=position)
        self.visible_ids = ids
        self._signature = signature
        self.empty.setVisible(not ids)
        if self.selected_id not in ids:
            self.selected_id = None
            if ids:
                self.select(ids[0])
        self._apply_filter()
