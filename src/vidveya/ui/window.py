import json
import os
from pathlib import Path
import subprocess
import uuid

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QFont, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .. import __version__
from ..auth import clear_cookies, import_cookies, vault_path
from ..engine import cleanup_staging
from ..models import FormatOption, STATE_LABELS, UserError
from ..paths import downloads_dir
from ..processes import WorkerThread
from ..store import Store, timestamp
from ..urls import normalize_url, validate_proxy


def label(text="", role="", wrap=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setObjectName(role)
    widget.setWordWrap(wrap)
    return widget


def button(text, callback=None, role=""):
    widget = QPushButton(text)
    widget.setObjectName(role)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if callback:
        widget.clicked.connect(callback)
    return widget


def size_text(value):
    if value is None:
        return "大小待确定"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024


def duration_text(seconds):
    seconds = max(0, int(seconds or 0))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


def codec_text(codec):
    for prefix, name in (("avc", "H.264"), ("av01", "AV1"), ("vp9", "VP9"), ("vp09", "VP9"), ("hev", "HEVC"), ("hvc", "HEVC")):
        if codec.startswith(prefix):
            return name
    return codec.split(".")[0]


class MainWindow(QMainWindow):
    def __init__(self, store: Store, start_diagnostics=True):
        super().__init__()
        self.store = store
        self.workers = []
        self.inspection = None
        self.downloader = None
        self.current_job = None
        self.video = None
        self.visible_options = []
        self.quick = False
        self.closing = False
        self.network = QNetworkAccessManager(self)
        self.thumbnail_reply = None
        self.ready = False
        self.setWindowTitle(f"VidVeya · YouTube 视频下载助手 {__version__}")
        self.resize(1080, 790)
        self.setMinimumSize(900, 690)
        self._build()
        self._restore_receipts()
        self.store.recover()
        self.refresh_history()
        if start_diagnostics:
            self.check_components()

    def _build(self):
        root = QWidget()
        root.setObjectName("Workspace")
        horizontal = QHBoxLayout(root)
        horizontal.setContentsMargins(0, 0, 0, 0)
        horizontal.setSpacing(0)
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(184)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(20, 30, 16, 22)
        side_layout.setSpacing(10)
        side_layout.addWidget(label("VidVeya", "Brand"))
        side_layout.addWidget(label("VIDEO SAVER", "Eyebrow"))
        side_layout.addSpacing(32)
        self.navigation = QButtonGroup(self)
        self.pages = QStackedWidget()
        for index, text in enumerate(("↓   新建下载", "▤   下载记录", "⚙   设置")):
            nav = button(text, role="Navigation")
            nav.setCheckable(True)
            self.navigation.addButton(nav, index)
            side_layout.addWidget(nav)
        self.navigation.idClicked.connect(self.pages.setCurrentIndex)
        self.navigation.button(0).setChecked(True)
        side_layout.addStretch()
        self.health_label = label("正在检查组件…", "Status", True)
        side_layout.addWidget(self.health_label)
        side_layout.addWidget(label(f"v{__version__}  ·  Windows", "Eyebrow"))
        horizontal.addWidget(side)
        horizontal.addWidget(self.pages, 1)
        self._build_download_page()
        self._build_history_page()
        self._build_settings_page()
        self.setCentralWidget(root)

    def page(self, heading, subtitle):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 24)
        layout.setSpacing(16)
        layout.addWidget(label(heading, "Heading"))
        layout.addWidget(label(subtitle, "Muted", True))
        self.pages.addWidget(page)
        return layout

    def _build_download_page(self):
        layout = self.page("把喜欢的视频，留在本地。", "粘贴 YouTube 或 Shorts 链接，选择清晰度，保留画面与声音。")
        link_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setAccessibleName("YouTube 视频链接")
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=…")
        self.url_input.returnPressed.connect(self.analyze)
        self.url_input.textEdited.connect(self.invalidate_video)
        link_row.addWidget(self.url_input, 1)
        link_row.addWidget(button("粘贴", self.paste))
        self.parse_button = button("解析视频", self.analyze, "Primary")
        link_row.addWidget(self.parse_button)
        layout.addLayout(link_row)
        self.notice = label("", "Notice", True)
        self.notice.hide()
        layout.addWidget(self.notice)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(18)
        self.thumbnail = label("▶")
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setFixedSize(152, 86)
        self.thumbnail.setStyleSheet("background: #F0F2F5; border-radius: 8px; color: #B7BDC8; font-size: 28px;")
        card_layout.addWidget(self.thumbnail)
        details = QVBoxLayout()
        self.video_title = label("等待添加视频", "Subheading", True)
        self.video_meta = label("支持普通视频与 Shorts", "Muted", True)
        details.addWidget(self.video_title)
        details.addWidget(self.video_meta)
        card_layout.addLayout(details, 1)
        layout.addWidget(card)

        modes = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        for index, title in enumerate(("快速下载", "高清下载")):
            control = button(title, role="Mode")
            control.setCheckable(True)
            self.mode_group.addButton(control, index)
            modes.addWidget(control)
        self.mode_group.button(1).setChecked(True)
        self.mode_group.idClicked.connect(self.change_mode)
        modes.addStretch()
        modes.addWidget(label("每个选项均包含音频", "Muted"))
        layout.addLayout(modes)
        self.formats = QTableWidget(0, 4)
        self.formats.setHorizontalHeaderLabels(["清晰度", "文件格式 / 编码", "帧率", "预计大小"])
        self.formats.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.formats.verticalHeader().hide()
        self.formats.verticalHeader().setDefaultSectionSize(47)
        self.formats.setShowGrid(False)
        self.formats.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.formats.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.formats.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.formats.itemSelectionChanged.connect(self.update_actions)
        self.formats.setMinimumHeight(170)
        layout.addWidget(self.formats, 1)
        self.format_hint = label("解析后显示源视频实际提供的清晰度。", "Muted", True)
        layout.addWidget(self.format_hint)

        self.progress_card = QFrame()
        self.progress_card.setObjectName("Card")
        progress_layout = QVBoxLayout(self.progress_card)
        self.progress_title = label("准备下载", "Subheading", True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(7)
        self.progress_meta = label("", "Muted")
        progress_layout.addWidget(self.progress_title)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_meta)
        self.progress_card.hide()
        layout.addWidget(self.progress_card)

        footer = QHBoxLayout()
        self.folder_label = label("", "Status")
        self.update_folder_label()
        footer.addWidget(self.folder_label, 1)
        self.cancel_button = button("取消下载", self.cancel_download)
        self.cancel_button.hide()
        footer.addWidget(self.cancel_button)
        self.download_button = button("下载所选视频", self.start_download, "Primary")
        self.download_button.setEnabled(False)
        footer.addWidget(self.download_button)
        layout.addLayout(footer)

    def _build_history_page(self):
        layout = self.page("下载记录", "成功下载的文件已验证视频轨和音频轨。")
        self.history = QTableWidget(0, 4)
        self.history.setHorizontalHeaderLabels(["视频", "清晰度", "状态", "创建时间"])
        self.history.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for index in range(1, 4):
            self.history.horizontalHeader().setSectionResizeMode(index, QHeaderView.ResizeMode.ResizeToContents)
        self.history.verticalHeader().hide()
        self.history.verticalHeader().setDefaultSectionSize(49)
        self.history.setShowGrid(False)
        self.history.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history.itemSelectionChanged.connect(self.select_history)
        layout.addWidget(self.history, 1)
        self.history_detail = label("尚无下载记录。", "Muted", True)
        layout.addWidget(self.history_detail)
        buttons = QHBoxLayout()
        self.reveal_button = button("打开所在文件夹", self.reveal_selected)
        self.retry_button = button("重新下载", self.retry_selected)
        self.reveal_button.setEnabled(False)
        self.retry_button.setEnabled(False)
        buttons.addWidget(self.reveal_button)
        buttons.addWidget(self.retry_button)
        buttons.addStretch()
        layout.addLayout(buttons)

    def _build_settings_page(self):
        layout = self.page("设置", "下载偏好与组件状态都保存在这台电脑上。")
        layout.addWidget(label("保存位置", "Subheading"))
        row = QHBoxLayout()
        self.directory_input = QLineEdit(self.directory())
        self.directory_input.setAccessibleName("下载保存位置")
        row.addWidget(self.directory_input, 1)
        row.addWidget(button("选择文件夹", self.choose_directory))
        layout.addLayout(row)
        layout.addWidget(label("代理地址（可选）", "Subheading"))
        self.proxy_input = QLineEdit(self.store.get_setting("proxy", ""))
        self.proxy_input.setAccessibleName("可选代理地址")
        self.proxy_input.setPlaceholderText("例如 http://127.0.0.1:7890；留空使用系统网络设置")
        layout.addWidget(self.proxy_input)
        layout.addWidget(label("浏览器中的代理扩展不会自动影响桌面助手。代理配置仅保存在本机。", "Muted", True))
        save_row = QHBoxLayout()
        save_row.addWidget(button("保存设置", self.save_settings, "Primary"))
        self.settings_notice = label("", "Muted", True)
        save_row.addWidget(self.settings_notice, 1)
        layout.addLayout(save_row)
        layout.addSpacing(8)
        layout.addWidget(label("YouTube 登录态", "Subheading"))
        auth_row = QHBoxLayout()
        self.auth_enabled = QCheckBox("使用已导入的登录态")
        self.auth_enabled.setChecked(bool(self.store.get_setting("use_auth", False) and vault_path().exists()))
        self.auth_enabled.toggled.connect(self.toggle_auth)
        auth_row.addWidget(self.auth_enabled)
        auth_row.addStretch()
        auth_row.addWidget(button("导入 Cookie", self.import_session))
        auth_row.addWidget(button("清除", self.clear_session))
        layout.addLayout(auth_row)
        self.auth_notice = label("已加密保存登录态，仅此 Windows 用户可读取。" if vault_path().exists()
                                 else "下载会员或私有视频时，请导入已有观看权限账号的 Netscape Cookie TXT。", "Muted", True)
        layout.addWidget(self.auth_notice)
        check_row = QHBoxLayout()
        check_row.addWidget(label("内置组件", "Subheading"))
        check_row.addStretch()
        self.check_button = button("重新检查", self.check_components)
        check_row.addWidget(self.check_button)
        layout.addLayout(check_row)
        self.component_table = QTableWidget(0, 2)
        self.component_table.setHorizontalHeaderLabels(["组件", "状态 / 版本"])
        self.component_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.component_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.component_table.verticalHeader().hide()
        self.component_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.component_table.setShowGrid(False)
        self.component_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self.component_table, 1)
        layout.addWidget(label("安装包已包含全部下载组件。更新应用时完整安装新版即可，下载文件和历史会保留。", "Muted", True))

    def directory(self):
        return self.store.get_setting("directory", str(downloads_dir()))

    def update_folder_label(self):
        text = self.directory()
        self.folder_label.setText("保存至 " + (text if len(text) < 48 else "…" + text[-45:]))
        self.folder_label.setToolTip(text)

    def show_notice(self, text):
        self.notice.setText(text)
        self.notice.setVisible(bool(text))

    def spawn(self, request, result, error):
        worker = WorkerThread(request, self)
        self.workers.append(worker)
        worker.result_received.connect(result)
        worker.error_received.connect(error)
        worker.finished.connect(lambda: self.worker_finished(worker))
        worker.start()
        return worker

    def worker_finished(self, worker):
        if worker is self.inspection:
            self.inspection = None
            self.parse_button.setText("解析视频")
            self.parse_button.setEnabled(self.ready)
        if worker is self.downloader:
            self.downloader = None
            self.cancel_button.hide()
        if worker in self.workers:
            self.workers.remove(worker)
        self.update_actions()
        worker.deleteLater()

    def invalidate_video(self):
        self.video = None
        self.formats.setRowCount(0)
        self.update_actions()

    def paste(self):
        from PySide6.QtWidgets import QApplication
        self.url_input.setText(QApplication.clipboard().text().strip())
        self.invalidate_video()

    def analyze(self):
        if self.inspection or not self.ready:
            if not self.ready:
                self.show_notice("请先在设置中确认内置组件可用。")
            return
        try:
            url = normalize_url(self.url_input.text())
        except UserError as error:
            self.show_notice(str(error))
            return
        self.invalidate_video()
        self.show_notice("")
        self.video_title.setText("正在读取视频信息…")
        self.video_meta.setText("正在查询可用清晰度和音轨")
        self.thumbnail.clear()
        self.parse_button.setEnabled(False)
        self.parse_button.setText("解析中…")
        self.inspection = self.spawn({"command": "analyze", "url": url, "proxy": self.store.get_setting("proxy", ""),
                                      "use_auth": self.store.get_setting("use_auth", False)},
                                     self.show_video, self.analysis_error)

    def analysis_error(self, message):
        self.show_notice(message)
        self.video_title.setText("暂时无法读取视频")
        self.video_meta.setText("检查链接和网络后重新解析")

    def show_video(self, info):
        self.video = info
        self.video_title.setText(info["title"])
        access = {"public": "公开视频", "unlisted": "不公开列出", "subscriber_only": "频道会员视频",
                  "premium_only": "付费视频", "private": "私有视频", "needs_auth": "已授权访问"}.get(info.get("availability"), "可访问")
        self.video_meta.setText(f"{info['channel']}  ·  {duration_text(info['duration'])}  ·  {access}")
        has_hd = any(option["resolution"] > 720 for option in info["options"])
        self.quick = not has_hd
        self.mode_group.button(0 if self.quick else 1).setChecked(True)
        self.fill_formats()
        self.load_thumbnail(info.get("thumbnail"))

    def load_thumbnail(self, url):
        if self.thumbnail_reply:
            self.thumbnail_reply.abort()
        self.thumbnail.setText("▶")
        if not url:
            return
        reply = self.network.get(QNetworkRequest(QUrl(url)))
        self.thumbnail_reply = reply
        reply.downloadProgress.connect(lambda count, total: reply.abort() if max(count, total) > 4 * 1024 * 1024 else None)
        def finish():
            if self.thumbnail_reply is reply:
                pixmap = QPixmap()
                if pixmap.loadFromData(bytes(reply.readAll())):
                    self.thumbnail.setPixmap(pixmap.scaled(self.thumbnail.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                          Qt.TransformationMode.SmoothTransformation))
                self.thumbnail_reply = None
            reply.deleteLater()
        reply.finished.connect(finish)

    def change_mode(self, index):
        self.quick = index == 0
        self.fill_formats()

    def fill_formats(self):
        options = [FormatOption(**item) for item in self.video["options"]] if self.video else []
        self.visible_options = [item for item in options if (item.resolution <= 720) == self.quick]
        self.formats.setRowCount(len(self.visible_options))
        for row, option in enumerate(self.visible_options):
            values = (option.label, f"{option.container.upper()} · {codec_text(option.video_codec)}",
                      f"{option.fps:g} fps" if option.fps else "—", size_text(option.estimated_bytes))
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                if column == 0:
                    item.setForeground(QColor("#CE2E37"))
                    font = QFont("Bahnschrift", 12)
                    font.setBold(True)
                    item.setFont(font)
                conversion = "\n高清 MP4 将转换为兼容 H.264；音频无损复制" if option.container == "mp4" and not option.video_codec.lower().startswith(("avc", "h264")) else "\n无损合并，不重新编码"
                item.setToolTip(f"{option.width} × {option.height}\n视频：{option.video_codec}\n音频：{option.audio_codec}{conversion}")
                self.formats.setItem(row, column, item)
        if self.visible_options:
            target = next((index for index, item in enumerate(self.visible_options) if item.resolution == (720 if self.quick else 1080) and item.container == "mp4"), 0)
            self.formats.selectRow(target)
        self.format_hint.setText("大小为估计值，实际下载后可能不同。高清 MP4 若源编码为 AV1 / VP9，会自动转换为兼容 H.264。" if options
                                 else "解析后显示源视频实际提供的清晰度。")
        if options and not self.visible_options:
            self.format_hint.setText("源视频未提供此档位，请切换下载方式。")
        self.update_actions()

    def update_actions(self):
        if not hasattr(self, "download_button"):
            return
        self.download_button.setEnabled(self.ready and self.video is not None and self.formats.currentRow() >= 0 and self.downloader is None)

    def start_download(self):
        if not self.ready or not self.video or self.downloader is not None:
            return
        row = self.formats.currentRow()
        if row < 0 or row >= len(self.visible_options):
            return
        self.start_job(self.video, self.visible_options[row].to_dict())

    def start_job(self, info, option):
        if self.downloader is not None or not self.ready:
            return
        job = {"id": str(uuid.uuid4()), "created": timestamp(), "url": info["url"], "title": info["title"],
               "option": option, "directory": self.directory(), "state": "starting", "error": ""}
        self.current_job = job
        self.store.save_job(job)
        self.refresh_history()
        self.show_notice("")
        self.progress_card.show()
        self.progress_title.setText("准备下载 · " + job["title"])
        self.progress_bar.setRange(0, 0)
        self.progress_meta.setText("正在刷新所选格式和音频")
        self.cancel_button.setText("取消下载")
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        worker = WorkerThread({"command": "download", "job_id": job["id"], "url": job["url"],
                               "option_key": option["key"], "directory": job["directory"],
                               "proxy": self.store.get_setting("proxy", ""),
                               "use_auth": self.store.get_setting("use_auth", False)}, self)
        self.downloader = worker
        self.workers.append(worker)
        worker.event_received.connect(self.show_progress)
        worker.result_received.connect(self.download_done)
        worker.error_received.connect(self.download_error)
        worker.cancelled_signal.connect(self.download_cancelled)
        worker.finished.connect(lambda: self.worker_finished(worker))
        worker.start()
        self.update_actions()

    def show_progress(self, event):
        if not self.current_job or self.closing:
            return
        state = event.get("state", "downloading")
        if state != self.current_job["state"]:
            self.current_job["state"] = state
            self.store.save_job(self.current_job)
            self.refresh_history()
        self.progress_title.setText(STATE_LABELS.get(state, state) + " · " + self.current_job["title"])
        percent = event.get("percent")
        if percent is None:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(percent))
        if state == "downloading":
            details = "已下载 " + size_text(event.get("downloaded_bytes", 0))
            if event.get("total_bytes"):
                details += " / " + size_text(event["total_bytes"])
            if event.get("speed"):
                details += "  ·  " + size_text(event["speed"]) + "/s"
            if event.get("eta") is not None:
                details += "  ·  剩余 " + duration_text(event["eta"])
            self.progress_meta.setText(details)
        else:
            self.progress_meta.setText({"starting": "正在刷新所选格式和音频", "merging": "正在无损合并画面与声音",
                                        "converting": "正在转换为兼容 H.264 MP4（音频无损复制）",
                                        "verifying": "正在检查视频轨、音频轨和时长"}.get(state, ""))

    def receipt(self, job):
        return Path(job["directory"]) / ".vidveya-tmp" / f"{job['id']}.completed.json"

    def recover_receipt(self, job):
        path = self.receipt(job)
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
            final = Path(result["path"])
            if final.is_file() and final.parent.resolve() == Path(job["directory"]).resolve() and result["verification"].get("audio_channels", 0) > 0:
                job.update(state="completed", result=result, error="")
                self.store.save_job(job)
                path.unlink()
                return True
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return False

    def _restore_receipts(self):
        for job in self.store.jobs():
            self.recover_receipt(job)

    def download_done(self, result):
        if not self.current_job:
            return
        self.current_job.update(state="completed", result=result, error="")
        self.store.save_job(self.current_job)
        self.receipt(self.current_job).unlink(missing_ok=True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_title.setText("下载完成 · 已验证画面与声音")
        self.progress_meta.setText(size_text(result["verification"]["bytes"]) + "  ·  " + Path(result["path"]).name)
        self.current_job = None
        self.refresh_history()

    def finish_unsuccessful(self, state, message):
        if not self.current_job:
            return
        job = self.current_job
        if self.recover_receipt(job):
            self.download_done(job["result"])
            return
        job.update(state=state, error=message)
        self.store.save_job(job)
        try:
            cleanup_staging(Path(job["directory"]), job["id"])
        except (OSError, ValueError, UserError):
            pass
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_title.setText(STATE_LABELS[state])
        self.progress_meta.setText("可在下载记录中重新下载")
        self.show_notice(message)
        self.current_job = None
        self.refresh_history()

    def download_error(self, message):
        self.finish_unsuccessful("failed", message)

    def cancel_download(self):
        if self.downloader:
            self.cancel_button.setEnabled(False)
            self.cancel_button.setText("正在取消…")
            self.downloader.cancel()

    def download_cancelled(self):
        self.finish_unsuccessful("interrupted" if self.closing else "cancelled",
                                 "应用退出，任务已中断。" if self.closing else "下载已取消，可在下载记录中重新下载。")

    def refresh_history(self):
        self.history_jobs = self.store.jobs()
        self.history.setRowCount(len(self.history_jobs))
        for row, job in enumerate(self.history_jobs):
            values = (job["title"], f"{job['option']['resolution']}P · {job['option']['container'].upper()}",
                      STATE_LABELS.get(job["state"], job["state"]), job["created"].replace("T", " ")[:16] + " UTC")
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                if column == 2 and job["state"] == "completed":
                    item.setForeground(QColor("#168A63"))
                self.history.setItem(row, column, item)
        self.history_detail.setText("选择记录查看详情。" if self.history_jobs else "尚无下载记录。")
        self.select_history()

    def selected_job(self):
        row = self.history.currentRow()
        return self.history_jobs[row] if 0 <= row < len(self.history_jobs) else None

    def select_history(self):
        if not hasattr(self, "reveal_button"):
            return
        job = self.selected_job()
        self.reveal_button.setEnabled(bool(job and job.get("result", {}).get("path")))
        self.retry_button.setEnabled(bool(job and job["state"] in {"completed", "failed", "cancelled", "interrupted"} and not self.downloader))
        if job:
            self.history_detail.setText(job.get("error") or job.get("result", {}).get("path", "任务正在进行"))

    def reveal_selected(self):
        job = self.selected_job()
        path = Path(job.get("result", {}).get("path", "")) if job else None
        if path and path.is_file():
            subprocess.Popen([str(Path(os.environ["SystemRoot"]) / "explorer.exe"), "/select,", str(path)])
        else:
            self.history_detail.setText("文件已被移动或删除。")

    def retry_selected(self):
        job = self.selected_job()
        if job and not self.downloader:
            self.pages.setCurrentIndex(0)
            self.navigation.button(0).setChecked(True)
            self.start_job({"url": job["url"], "title": job["title"]}, job["option"])

    def choose_directory(self):
        chosen = QFileDialog.getExistingDirectory(self, "选择下载保存位置", self.directory_input.text())
        if chosen:
            self.directory_input.setText(chosen)

    def save_settings(self):
        try:
            proxy = validate_proxy(self.proxy_input.text())
            if not self.directory_input.text().strip():
                raise UserError("请选择保存目录。")
            directory = Path(self.directory_input.text()).expanduser()
            if not directory.is_absolute():
                raise UserError("请选择完整的保存目录路径。")
            directory.mkdir(parents=True, exist_ok=True)
            self.store.set_setting("directory", str(directory.resolve()))
            self.store.set_setting("proxy", proxy)
            self.update_folder_label()
            self.settings_notice.setText("已保存，下次下载使用新设置。")
        except (UserError, OSError) as error:
            self.settings_notice.setText(str(error))

    def toggle_auth(self, checked):
        if checked and not vault_path().exists():
            self.auth_enabled.setChecked(False)
            self.auth_notice.setText("请先导入有观看权限账号的 YouTube Cookie 文件。")
            return
        self.store.set_setting("use_auth", checked)

    def import_session(self):
        filename, _ = QFileDialog.getOpenFileName(self, "导入 YouTube Cookie（Netscape 格式）", "", "Cookie 文本 (*.txt);;所有文件 (*)")
        if not filename:
            return
        try:
            count = import_cookies(Path(filename))
            self.auth_enabled.setChecked(True)
            self.store.set_setting("use_auth", True)
            self.auth_notice.setText(f"已加密保存 {count} 条 YouTube Cookie。是否有会员权限以服务器校验为准；登录失效时请重新导入。")
        except (UserError, OSError) as error:
            self.auth_notice.setText(str(error))

    def clear_session(self):
        try:
            clear_cookies()
            self.auth_enabled.setChecked(False)
            self.store.set_setting("use_auth", False)
            self.auth_notice.setText("已清除本机保存的登录态，后续任务使用未登录访问。")
        except OSError:
            self.auth_notice.setText("无法清除登录态，请关闭下载后重试。")

    def check_components(self):
        if not hasattr(self, "check_button") or not self.check_button.isEnabled():
            return
        self.check_button.setEnabled(False)
        self.check_button.setText("检查中…")
        self.parse_button.setEnabled(False)
        self.spawn({"command": "diagnostics"}, self.components_checked, self.component_error)

    def components_checked(self, result):
        self.component_table.setRowCount(len(result))
        for row, (name, status) in enumerate(result.items()):
            self.component_table.setItem(row, 0, QTableWidgetItem(name))
            item = QTableWidgetItem(("可用  ·  " if status["ok"] else "异常  ·  ") + status["version"])
            item.setToolTip(item.text())
            item.setForeground(QColor("#168A63" if status["ok"] else "#CE2E37"))
            self.component_table.setItem(row, 1, item)
        self.ready = bool(result) and all(status["ok"] for status in result.values())
        self.health_label.setText("●  下载组件就绪" if self.ready else "●  请检查内置组件")
        self.check_button.setEnabled(True)
        self.check_button.setText("重新检查")
        self.parse_button.setEnabled(self.ready and not self.inspection)
        if not self.ready:
            self.show_notice("部分内置组件不可用，请在设置中查看详情，或重新完整安装。")
        self.update_actions()

    def component_error(self, message):
        self.ready = False
        self.health_label.setText("●  组件检查失败")
        self.check_button.setEnabled(True)
        self.check_button.setText("重新检查")
        self.show_notice(message)
        self.update_actions()

    def closeEvent(self, event):
        if self.downloader and self.downloader.isRunning():
            answer = QMessageBox.question(self, "正在下载", "退出会中断当前下载。可最小化窗口继续下载。\n\n确定退出？",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                          QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.closing = True
        for worker in list(self.workers):
            worker.cancel()
        for worker in list(self.workers):
            worker.wait(10000)
        if self.current_job:
            self.finish_unsuccessful("interrupted", "应用退出，任务已中断。可以重新下载。")
        if self.thumbnail_reply:
            self.thumbnail_reply.abort()
        event.accept()
