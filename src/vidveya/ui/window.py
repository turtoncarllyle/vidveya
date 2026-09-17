from datetime import datetime
import os
from pathlib import Path
import subprocess
import time

from PySide6.QtCore import QEvent, QSignalBlocker, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListView, QMainWindow, QMenu, QMessageBox, QProgressBar, QPushButton, QSpinBox,
    QScrollArea, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .. import __version__
from ..auth import clear_cookies, import_cookies, vault_path
from ..i18n import set_language, t
from ..models import ACTIVE_STATES, FormatOption, STATE_LABELS, UserError
from ..paths import downloads_dir
from ..processes import WorkerThread
from ..store import Store
from ..tasks import DownloadManager, bounded_int
from ..urls import normalize_url, validate_proxy
from .formatting import codec_text, duration_text, size_text
from .notifications import CompletionNotifier, play_completion_sound
from .transfers_page import TransfersPage
from .style import get_theme_stylesheet, resolve_theme


def format_local_datetime(iso_str: str) -> str:
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        local_dt = dt.astimezone()
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        clean = iso_str.replace("T", " ")
        if "+" in clean:
            clean = clean.split("+")[0]
        return clean[:19]


def combo_box(accessible_name="", scroll=False):
    box = QComboBox()
    view = QListView()
    view.setUniformItemSizes(True)
    view.setVerticalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAsNeeded if scroll else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    box.setView(view)
    if accessible_name:
        box.setAccessibleName(accessible_name)
    return box


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


class QualityChipWidget(QFrame):
    clicked = Signal(int)

    def __init__(self, index: int, option: FormatOption, is_recommended: bool = False, parent=None):
        super().__init__(parent)
        self.index = index
        self.setObjectName("QualityCard")
        self.setProperty("selected", "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(96)

        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(14, 10, 14, 10)
        card_layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        res_label = QLabel(option.label)
        res_label.setObjectName("QualityRes")
        top_row.addWidget(res_label)

        if is_recommended:
            badge = QLabel(t("dl_recommended", "推荐"))
            badge.setObjectName("QualityBadge")
            top_row.addWidget(badge)

        top_row.addStretch()

        size_str = size_text(option.estimated_bytes)
        if option.estimated_bytes is not None:
            size_str = f"≈ {size_str}"
        size_label = QLabel(size_str)
        size_label.setObjectName("QualitySize")
        size_label.setToolTip(t("dl_th_size", "预计大小"))
        top_row.addWidget(size_label)
        card_layout.addLayout(top_row)

        fps_str = f"{option.fps:g} FPS" if option.fps else t("dl_fps_unknown", "帧率未知")
        dimensions_str = f"{option.width}×{option.height} · {fps_str}"
        card_layout.addWidget(label(dimensions_str, "QualityDimensions"))

        meta_str = f"{option.container.upper()} · {codec_text(option.video_codec)}"
        meta_label = QLabel(meta_str)
        meta_label.setObjectName("QualityMeta")
        card_layout.addWidget(meta_label)
        self.setToolTip(f"{option.label}\n{dimensions_str}\n{meta_str}\n{size_str}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    NEW_PAGE, TRANSFERS_PAGE, SETTINGS_PAGE = range(3)

    @staticmethod
    def combo_box(accessible_name="", scroll=False):
        return combo_box(accessible_name, scroll)

    def __init__(self, store: Store, start_diagnostics=True):
        super().__init__()
        self.store = store
        self.workers = []
        self.inspection = None
        self._analysis_url = None
        self._pending_analysis = False
        self.downloads = DownloadManager(store, self)
        self._history_states = {}
        self._last_sound_at = float('-inf')
        self.video = None
        self.visible_options = []
        self.quick = False
        self.closing = False
        self._exit_requested = False
        self.network = QNetworkAccessManager(self)
        self.thumbnail_reply = None
        self.ready = False
        self.quality_chips = []
        self._dismissed_clipboard = None
        self._sniffed_text = "" 

        # 初始化主题与语言（默认跟随系统）
        self.current_theme_setting = self.store.get_setting("theme", "system")
        self.current_lang_setting = self.store.get_setting("language", "system")
        set_language(self.current_lang_setting)

        self.completion_notifier = CompletionNotifier(self, self.store.get_setting("completion_notification", False))
        self.completion_notifier.activated.connect(self.show_completed_tasks)
        self.completion_notifier.open_file_requested.connect(self.open_completed_file)
        self.completion_notifier.open_folder_requested.connect(self.open_completed_folder)

        self.setWindowTitle(f"{t('app_title', 'VidVeya · YouTube 视频下载助手')} {__version__}")
        self.resize(1120, 820)
        self.setMinimumSize(940, 720)
        self._build()
        self.apply_theme(self.current_theme_setting)
        self.downloads.job_changed.connect(self.on_job_changed)
        self.downloads.job_removed.connect(self.on_job_removed)
        self.downloads.summary_changed.connect(self.update_task_summary)
        self.downloads.completed.connect(self.on_task_completed)
        self.downloads.drained.connect(self.maybe_finish_close)
        self.refresh_history()
        self.update_task_summary()
        if start_diagnostics:
            self.check_components()

    def apply_theme(self, theme="system"):
        self.current_theme_setting = theme
        from PySide6.QtWidgets import QApplication
        sheet = get_theme_stylesheet(theme)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(sheet)
        else:
            self.setStyleSheet(sheet)
        if hasattr(self, "theme_toggle_btn"):
            actual = resolve_theme(theme)
            self.theme_toggle_btn.setText("☀️" if actual == "dark" else "🌙")
            self.theme_toggle_btn.setToolTip("切换为浅色模式" if actual == "dark" else "切换为深色模式")

    def toggle_theme_quick(self):
        actual = resolve_theme(self.current_theme_setting)
        next_theme = "light" if actual == "dark" else "dark"
        self.store.set_setting("theme", next_theme)
        self.apply_theme(next_theme)
        if hasattr(self, "theme_input"):
            idx = self.theme_input.findData(next_theme)
            if idx >= 0:
                self.theme_input.setCurrentIndex(idx)

    def _build(self):
        root = QWidget()
        root.setObjectName("Workspace")
        horizontal = QHBoxLayout(root)
        horizontal.setContentsMargins(0, 0, 0, 0)
        horizontal.setSpacing(0)

        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(208)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(18, 24, 16, 20)
        side_layout.setSpacing(10)

        brand_row = QHBoxLayout()
        brand_col = QVBoxLayout()
        brand_col.setSpacing(2)
        brand_col.addWidget(label("VidVeya", "Brand"))
        brand_col.addWidget(label("VIDEO SAVER", "Eyebrow"))
        brand_row.addLayout(brand_col, 1)

        self.theme_toggle_btn = button("🌙", self.toggle_theme_quick)
        self.theme_toggle_btn.setFixedSize(36, 36)
        self.theme_toggle_btn.setToolTip("切换界面主题")
        self.theme_toggle_btn.setStyleSheet("border-radius: 18px; padding: 0; font-size: 16px;")
        brand_row.addWidget(self.theme_toggle_btn)
        side_layout.addLayout(brand_row)

        side_layout.addSpacing(24)

        self.navigation = QButtonGroup(self)
        self.pages = QStackedWidget()
        nav_items = (
            t("nav_new", "↓   新建下载"),
            t("nav_transfers", "⇋   传输列表"),
            t("nav_settings", "⚙   设置"),
        )
        for index, text in enumerate(nav_items):
            nav = button(text, role="Navigation")
            nav.setCheckable(True)
            self.navigation.addButton(nav, index)
            side_layout.addWidget(nav)
        self.navigation.idClicked.connect(self.show_page)
        self.pages.currentChanged.connect(lambda index: self.navigation.button(index).setChecked(True) if self.navigation.button(index) else None)
        self.navigation.button(0).setChecked(True)

        side_layout.addStretch()

        self.sidebar_mini_task = QFrame()
        self.sidebar_mini_task.setObjectName("SidebarMiniTask")
        self.sidebar_mini_task.setCursor(Qt.CursorShape.PointingHandCursor)
        mini_layout = QVBoxLayout(self.sidebar_mini_task)
        mini_layout.setContentsMargins(12, 10, 12, 10)
        mini_layout.setSpacing(6)
        self.mini_title = label(t("mini_task_title", "下载中"), "Status", True)
        self.mini_title.setStyleSheet("font-size: 11px; font-weight: 600;")
        self.mini_progress = QProgressBar()
        self.mini_progress.setFixedHeight(6)
        self.mini_progress.setTextVisible(False)
        self.mini_status = label("", "Eyebrow")
        mini_layout.addWidget(self.mini_title)
        mini_layout.addWidget(self.mini_progress)
        mini_layout.addWidget(self.mini_status)
        self.sidebar_mini_task.mousePressEvent = lambda e: self.show_tasks()
        self.sidebar_mini_task.hide()
        side_layout.addWidget(self.sidebar_mini_task)

        footer_frame = QFrame()
        footer_layout = QVBoxLayout(footer_frame)
        footer_layout.setContentsMargins(0, 8, 0, 0)
        footer_layout.setSpacing(6)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(148, 163, 184, 0.25); border: none;")
        footer_layout.addWidget(sep)

        self.health_label = label(t("nav_checking", "正在检查组件…"), "Status", True)
        self.health_label.setStyleSheet("font-size: 11px; padding: 2px 4px;")
        footer_layout.addWidget(self.health_label)

        version_lbl = label(f"v{__version__}  ·  Windows", "Eyebrow")
        version_lbl.setStyleSheet("padding: 0 4px;")
        footer_layout.addWidget(version_lbl)

        side_layout.addWidget(footer_frame)

        horizontal.addWidget(side)
        horizontal.addWidget(self.pages, 1)
        self._build_download_page()

        self.transfers_page = TransfersPage(self)
        self.pages.addWidget(self.transfers_page)

        # 映射向后兼容属性供其他模块与测试直接访问
        self.task_list = self.transfers_page.task_list
        self.history = self.transfers_page.history
        self.history_detail = self.transfers_page.history_detail
        self.history_count_label = self.transfers_page.history_count_label
        self.sort_combo = self.transfers_page.sort_combo
        self.search_input = self.transfers_page.search_input
        self.clear_history_button = self.transfers_page.clear_history_button
        self.delete_history_button = self.transfers_page.delete_history_button
        self.reveal_button = self.transfers_page.reveal_button
        self.play_history_button = self.transfers_page.play_history_button
        self.retry_button = self.transfers_page.retry_button
        self.resume_queue_button = self.transfers_page.resume_all_btn
        self.task_summary = self.transfers_page.task_summary
        self.history_delete_shortcut = self.transfers_page.history_delete_shortcut
        self.history_actions_widget = self.transfers_page.compat_actions
        self.current_sort_column = 3
        self.current_sort_order = Qt.SortOrder.DescendingOrder

        self.task_list.cancel_requested.connect(self.downloads.cancel)
        self.task_list.retry_requested.connect(self.retry_task)
        self.task_list.play_requested.connect(self.play_task)
        self.task_list.reveal_requested.connect(self.reveal_task)

        self._build_settings_page()
        self.setCentralWidget(root)

    def page(self, heading, subtitle, scroll=False):
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 26)
        layout.setSpacing(16)
        layout.addWidget(label(heading, "Heading"))
        layout.addWidget(label(subtitle, "Muted", True))
        if scroll:
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            area.setWidget(page)
            self.pages.addWidget(area)
        else:
            self.pages.addWidget(page)
        return layout

    def _build_download_page(self):
        layout = self.page(t("dl_heading", "把喜欢的视频，留在本地。"),
                           t("dl_subtitle", "粘贴 YouTube 或 Shorts 链接，选择清晰度，保留画面与声音。"), scroll=True)

        # 集成式 Hero 链接输入胶囊
        self.hero_box = QFrame()
        self.hero_box.setObjectName("HeroInput")
        hero_layout = QHBoxLayout(self.hero_box)
        hero_layout.setContentsMargins(14, 8, 10, 8)
        hero_layout.setSpacing(8)

        self.url_icon = label("🔗")
        self.url_icon.setStyleSheet("font-size: 15px; color: #94A3B8; background: transparent;")
        hero_layout.addWidget(self.url_icon)

        self.url_input = QLineEdit()
        self.url_input.setObjectName("HeroUrlInput")
        self.url_input.setAccessibleName("YouTube 视频链接")
        self.url_input.setPlaceholderText(t("dl_url_placeholder", "https://www.youtube.com/watch?v=…"))
        self.url_input.returnPressed.connect(self.analyze)
        self.url_input.textChanged.connect(self._on_url_text_changed)
        self.url_input.installEventFilter(self)
        hero_layout.addWidget(self.url_input, 1)

        self.clipboard_badge = label(t("dl_clipboard_detected", "已识别剪贴板中的视频链接"), "Badge")
        self.clipboard_badge.setObjectName("ClipboardBadge")
        self.clipboard_badge.hide()
        hero_layout.addWidget(self.clipboard_badge)

        self.clear_btn = QPushButton("✕")
        self.clear_btn.setObjectName("ClearButton")
        self.clear_btn.setToolTip(t("dl_clear", "清空"))
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear_url)
        self.clear_btn.hide()
        hero_layout.addWidget(self.clear_btn)

        self.paste_btn = button(t("dl_paste", "粘贴"), self.paste_smart)
        hero_layout.addWidget(self.paste_btn)

        self.parse_button = button(t("dl_analyze", "解析视频"), self.analyze, "Primary")
        hero_layout.addWidget(self.parse_button)
        layout.addWidget(self.hero_box)

        # 原地反馈横幅
        self.added_actions = QFrame()
        self.added_actions.setObjectName("AddedBanner")
        added_layout = QHBoxLayout(self.added_actions)
        added_layout.setContentsMargins(18, 12, 18, 12)
        added_layout.setSpacing(14)

        self.added_banner_label = label("✓  " + t("dl_added_banner", "任务已加入下载队列"), "Subheading", True)
        self.added_banner_label.setObjectName("AddedBannerLabel")
        added_layout.addWidget(self.added_banner_label, 1)

        self.view_transfers_btn = button(t("dl_view_transfers", "查看传输列表 ➔"), self.go_to_transfers)
        added_layout.addWidget(self.view_transfers_btn)

        self.continue_add_btn = button(t("dl_continue", "继续添加"), self.reset_for_next)
        added_layout.addWidget(self.continue_add_btn)

        self.added_actions.hide()
        layout.addWidget(self.added_actions)

        self.notice = label("", "Notice", True)
        self.notice.hide()
        layout.addWidget(self.notice)

        # 居中引导空状态
        self.empty_placeholder = QFrame()
        self.empty_placeholder.setObjectName("SubCard")
        empty_layout = QVBoxLayout(self.empty_placeholder)
        empty_layout.setContentsMargins(32, 44, 32, 44)
        empty_layout.setSpacing(12)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_icon = label("🎬")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon.setStyleSheet("font-size: 36px; background: transparent;")
        empty_layout.addWidget(empty_icon)

        self.empty_guide_title = label(t("dl_empty_guide", "复制 YouTube 视频链接，在此处开始下载"), "Subheading")
        self.empty_guide_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_guide_title)

        self.empty_guide_subtitle = label(t("dl_empty_sub", "支持普通视频与 Shorts，粘贴链接即可极速解析与下载"), "Muted")
        self.empty_guide_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_guide_subtitle)

        layout.addWidget(self.empty_placeholder)

        # 视频详情卡片
        self.video_card = QFrame()
        self.video_card.setObjectName("Card")
        card_layout = QHBoxLayout(self.video_card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(20)

        self.thumbnail = label("▶")
        self.thumbnail.setObjectName("ThumbnailPlaceholder")
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setFixedSize(160, 92)
        card_layout.addWidget(self.thumbnail)

        details = QVBoxLayout()
        details.setSpacing(6)
        self.video_title = label(t("dl_waiting_title", "等待添加视频"), "Subheading", True)
        self.video_meta = label(t("dl_waiting_meta", "支持普通视频与 Shorts"), "Muted", True)
        details.addWidget(self.video_title)
        details.addWidget(self.video_meta)
        card_layout.addLayout(details, 1)
        self.video_card.hide()
        layout.addWidget(self.video_card)

        # 模式切换与画质选择栏
        self.modes_widget = QWidget()
        modes = QHBoxLayout(self.modes_widget)
        modes.setContentsMargins(0, 0, 0, 0)
        self.quality_title_label = label(t("dl_quality_title", "选择下载清晰度"), "Section")
        modes.addWidget(self.quality_title_label)
        modes.addSpacing(16)

        self.mode_group = QButtonGroup(self)
        for index, title in enumerate((t("dl_mode_quick", "快速下载"), t("dl_mode_hd", "高清下载"))):
            control = button(title, role="Mode")
            control.setCheckable(True)
            self.mode_group.addButton(control, index)
            modes.addWidget(control)
        self.mode_group.button(1).setChecked(True)
        self.mode_group.idClicked.connect(self.change_mode)
        modes.addStretch()
        modes.addWidget(label(t("dl_audio_note", "每个选项均包含音频"), "Muted"))
        self.modes_widget.hide()
        layout.addWidget(self.modes_widget)

        # 现代画质芯片网格容器
        self.chips_widget = QWidget()
        self.chips_layout = QGridLayout(self.chips_widget)
        self.chips_layout.setContentsMargins(0, 0, 0, 0)
        self.chips_layout.setSpacing(10)
        self.chips_widget.hide()
        layout.addWidget(self.chips_widget)

        # 格式列表（表格美化，圆角且行高舒适；默认折叠以芯片卡片为主，保持底层测试与高级参数兼容）
        self.formats = QTableWidget(0, 4)
        self.formats.setHorizontalHeaderLabels([
            t("dl_th_res", "清晰度"),
            t("dl_th_format", "文件格式 / 编码"),
            t("dl_th_fps", "帧率"),
            t("dl_th_size", "预计大小")
        ])
        self.formats.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.formats.verticalHeader().hide()
        self.formats.verticalHeader().setDefaultSectionSize(48)
        self.formats.setShowGrid(False)
        self.formats.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.formats.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.formats.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.formats.itemSelectionChanged.connect(self.update_actions)
        self.formats.setMinimumHeight(130)
        self.formats.hide()
        layout.addWidget(self.formats)

        self.format_hint = label(t("dl_hint_idle", "解析后显示源视频实际提供的清晰度。"), "Muted", True)
        self.format_hint.hide()
        layout.addWidget(self.format_hint)

        # 底部操作栏
        footer = QHBoxLayout()
        self.folder_label = label("", "Status")
        self.update_folder_label()
        footer.addWidget(self.folder_label, 1)

        self.download_button = button(t("task_add"), self.start_download, "Primary")
        self.download_button.setEnabled(False)
        footer.addWidget(self.download_button)
        layout.addLayout(footer)

    def show_page(self, index):
        self.pages.setCurrentIndex(index)
        btn = self.navigation.button(index)
        if btn:
            btn.setChecked(True)

    def show_tasks(self):
        self.show_page(self.TRANSFERS_PAGE)
        self.transfers_page.switch_to_active()

    def show_history(self):
        self.show_page(self.TRANSFERS_PAGE)
        self.transfers_page.switch_to_history()

    def continue_adding(self):
        self.clear_url()
        self.added_actions.hide()
        self.url_input.setFocus()

    def _build_settings_page(self):
        layout = self.page(t("set_heading", "设置"),
                           t("set_subtitle", "下载偏好与组件状态都保存在这台电脑上。"), scroll=True)

        # 1. 外观与偏好卡片 (Appearance & General)
        pref_card = QFrame()
        pref_card.setObjectName("Card")
        pref_layout = QVBoxLayout(pref_card)
        pref_layout.setContentsMargins(20, 18, 20, 18)
        pref_layout.setSpacing(14)
        pref_layout.addWidget(label(t("set_sec_appearance", "外观与偏好"), "Subheading"))

        pref_grid = QGridLayout()
        pref_grid.setHorizontalSpacing(14)
        pref_grid.setVerticalSpacing(12)

        pref_grid.addWidget(label(t("set_theme_label", "界面主题") + "：", wrap=True), 0, 0)
        self.theme_input = combo_box("界面主题")
        self.theme_input.addItem(t("set_theme_system", "跟随操作系统"), "system")
        self.theme_input.addItem(t("set_theme_light", "浅色模式"), "light")
        self.theme_input.addItem(t("set_theme_dark", "深色模式"), "dark")
        current_theme = self.store.get_setting("theme", "system")
        idx = self.theme_input.findData(current_theme)
        if idx >= 0:
            self.theme_input.setCurrentIndex(idx)
        self.theme_input.currentIndexChanged.connect(self.on_theme_changed)
        pref_grid.addWidget(self.theme_input, 0, 1)

        pref_grid.addWidget(label(t("set_lang_label", "界面语言") + "：", wrap=True), 0, 2)
        self.language_input = combo_box("界面语言")
        self.language_input.addItem(t("set_lang_system", "跟随操作系统"), "system")
        self.language_input.addItem(t("set_lang_zh", "简体中文"), "zh")
        self.language_input.addItem(t("set_lang_en", "English"), "en")
        current_lang = self.store.get_setting("language", "system")
        idx_lang = self.language_input.findData(current_lang)
        if idx_lang >= 0:
            self.language_input.setCurrentIndex(idx_lang)
        self.language_input.currentIndexChanged.connect(self.on_language_changed)
        pref_grid.addWidget(self.language_input, 0, 3)

        pref_grid.addWidget(label(t("set_sec_window", "关闭窗口时") + "：", wrap=True), 1, 0)
        self.close_action_input = combo_box("关闭窗口时的操作")
        self.close_action_input.addItem(t("set_close_minimize", "最小化到任务栏（继续下载）"), "minimize")
        self.close_action_input.addItem(t("set_close_exit", "退出软件"), "exit")
        self.close_action_input.setCurrentIndex(1 if self.store.get_setting("close_action") == "exit" else 0)
        self.close_action_input.currentIndexChanged.connect(lambda _: self.auto_save())
        pref_grid.addWidget(self.close_action_input, 1, 1)

        self.close_prompt_input = QCheckBox(t("set_close_prompt", "关闭时显示操作提示"))
        self.close_prompt_input.setChecked(self.store.get_setting("confirm_close", True))
        self.close_prompt_input.toggled.connect(lambda _: self.auto_save())
        pref_grid.addWidget(self.close_prompt_input, 1, 2, 1, 2)

        for control in (self.theme_input, self.language_input, self.close_action_input):
            control.setMinimumContentsLength(12)
            control.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            control.setToolTip(control.currentText())
            control.currentTextChanged.connect(control.setToolTip)

        pref_grid.setColumnStretch(1, 1)
        pref_grid.setColumnStretch(3, 1)
        pref_layout.addLayout(pref_grid)
        pref_layout.addWidget(label(t("set_close_note", "最小化后可从任务栏恢复窗口；可随时在设置中更改此行为。"), "Muted", True))
        layout.addWidget(pref_card)

        # 2. 下载与调度卡片 (Downloads & Concurrency)
        sched_card = QFrame()
        sched_card.setObjectName("Card")
        sched_layout = QVBoxLayout(sched_card)
        sched_layout.setContentsMargins(20, 18, 20, 18)
        sched_layout.setSpacing(14)
        sched_layout.addWidget(label(t("task_heading", "下载与调度"), "Subheading"))

        sched_grid = QGridLayout()
        sched_grid.setHorizontalSpacing(14)
        sched_grid.setVerticalSpacing(12)

        sched_grid.addWidget(label(t("set_parallel") + "：", wrap=True), 0, 0)
        self.parallel_input = QSpinBox()
        self.parallel_input.setRange(1, 5)
        self.parallel_input.setValue(self.downloads.max_parallel)
        self.parallel_input.setAccessibleName(t("set_parallel"))
        self.parallel_input.valueChanged.connect(self.downloads.set_max_parallel)
        sched_grid.addWidget(self.parallel_input, 0, 1)

        sched_grid.addWidget(label(t("set_retries") + "：", wrap=True), 0, 2)
        self.retry_count_input = QSpinBox()
        self.retry_count_input.setRange(0, 10)
        self.retry_count_input.setValue(bounded_int(self.store.get_setting("auto_retry_count", 3), 3, 0, 10))
        self.retry_count_input.setAccessibleName(t("set_retries"))
        self.retry_count_input.valueChanged.connect(lambda value: self.store.set_setting("auto_retry_count", value))
        sched_grid.addWidget(self.retry_count_input, 0, 3)

        sched_grid.addWidget(label(t("set_retries_note"), "Muted", True), 1, 0, 1, 4)

        sched_grid.addWidget(label(t("set_sound_label", "完成提醒") + "：", wrap=True), 2, 0)
        self.completion_sound_input = QCheckBox(t("set_completion_sound", "下载完成后播放提示音"))
        self.completion_sound_input.setChecked(self.store.get_setting("completion_sound", True))
        self.completion_sound_input.setToolTip(t(
            "set_completion_sound_note", "校验画面、声音和时长通过后提醒，最小化时也会播放。"
        ))
        self.completion_sound_input.toggled.connect(self.on_completion_sound_changed)
        sched_grid.addWidget(self.completion_sound_input, 2, 1, 1, 3)

        self.completion_notification_input = QCheckBox(t("set_completion_notification"))
        self.completion_notification_input.setChecked(self.store.get_setting("completion_notification", False))
        self.completion_notification_input.setToolTip(t("set_completion_notification_note"))
        self.completion_notification_input.toggled.connect(self.on_completion_notification_changed)
        sched_grid.addWidget(self.completion_notification_input, 3, 1, 1, 3)

        sched_grid.setColumnStretch(1, 1)
        sched_grid.setColumnStretch(3, 1)
        sched_layout.addLayout(sched_grid)
        layout.addWidget(sched_card)

        # 3. 存储与网络卡片 (Storage & Network)
        storage_card = QFrame()
        storage_card.setObjectName("Card")
        storage_layout = QVBoxLayout(storage_card)
        storage_layout.setContentsMargins(20, 18, 20, 18)
        storage_layout.setSpacing(12)
        storage_layout.addWidget(label(t("set_sec_storage", "存储与网络"), "Subheading"))

        dir_row = QHBoxLayout()
        dir_row.addWidget(label(t("dl_save_to", "保存至") + "："))
        self.directory_input = QLineEdit(self.directory())
        self.directory_input.setAccessibleName("下载保存位置")
        self.directory_input.textChanged.connect(lambda _: self.auto_save())
        dir_row.addWidget(self.directory_input, 1)
        dir_row.addWidget(button(t("set_btn_choose_dir", "选择文件夹"), self.choose_directory))
        storage_layout.addLayout(dir_row)

        proxy_row = QHBoxLayout()
        proxy_row.addWidget(label(t("set_sec_proxy", "代理地址") + "："))
        self.proxy_input = QLineEdit(self.store.get_setting("proxy", ""))
        self.proxy_input.setAccessibleName("可选代理地址")
        self.proxy_input.setPlaceholderText(t("set_proxy_placeholder", "例如 http://127.0.0.1:7890；留空使用系统网络设置"))
        self.proxy_input.editingFinished.connect(self.auto_save)
        proxy_row.addWidget(self.proxy_input, 1)
        storage_layout.addLayout(proxy_row)
        storage_layout.addWidget(label(t("set_proxy_note", "浏览器中的代理扩展不会自动影响桌面助手。代理配置仅保存在本机。"), "Muted", True))
        layout.addWidget(storage_card)

        # 4. 凭据与组件卡片 (Credentials & Diagnostics)
        diag_card = QFrame()
        diag_card.setObjectName("Card")
        diag_layout = QVBoxLayout(diag_card)
        diag_layout.setContentsMargins(20, 18, 20, 18)
        diag_layout.setSpacing(12)

        auth_header = QHBoxLayout()
        auth_header.addWidget(label(t("set_sec_auth", "YouTube 登录态与组件"), "Subheading"))
        auth_header.addStretch()
        self.cookie_help_btn = button("📖 " + t("set_btn_cookie_help", "如何导入 Cookie？"), self.show_cookie_help)
        self.cookie_help_btn.setStyleSheet("border-radius: 6px; padding: 4px 10px; font-size: 13px; color: #E53935;")
        auth_header.addWidget(self.cookie_help_btn)
        diag_layout.addLayout(auth_header)

        auth_row = QHBoxLayout()
        self.auth_enabled = QCheckBox(t("set_auth_use", "使用已导入的登录态"))
        self.auth_enabled.setChecked(bool(self.store.get_setting("use_auth", False) and vault_path().exists()))
        self.auth_enabled.toggled.connect(self.toggle_auth)
        auth_row.addWidget(self.auth_enabled)
        auth_row.addStretch()
        auth_row.addWidget(button(t("set_btn_import", "导入 Cookie"), self.import_session))
        auth_row.addWidget(button(t("set_btn_clear", "清除"), self.clear_session))
        diag_layout.addLayout(auth_row)

        self.auth_notice = label(t("set_auth_notice_saved", "已加密保存登录态，仅此 Windows 用户可读取。") if vault_path().exists()
                                 else t("set_auth_notice_empty", "下载会员或私有视频时，请导入已有观看权限账号的 Netscape Cookie TXT。"), "Muted", True)
        diag_layout.addWidget(self.auth_notice)

        diag_layout.addSpacing(8)
        check_row = QHBoxLayout()
        check_row.addWidget(label(t("set_sec_components", "内置组件"), "Subheading"))
        check_row.addStretch()
        self.check_button = button(t("set_btn_recheck", "重新检查"), self.check_components)
        check_row.addWidget(self.check_button)
        diag_layout.addLayout(check_row)

        self.component_table = QTableWidget(0, 2)
        self.component_table.setHorizontalHeaderLabels([t("set_comp_th_name", "组件"), t("set_comp_th_status", "状态 / 版本")])
        self.component_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.component_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.component_table.verticalHeader().hide()
        self.component_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.component_table.setShowGrid(False)
        self.component_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.component_table.setMinimumHeight(180)
        diag_layout.addWidget(self.component_table, 1)
        diag_layout.addWidget(label(t("set_comp_note", "安装包已包含全部下载组件。更新应用时完整安装新版即可，下载文件和历史会保留。"), "Muted", True))
        layout.addWidget(diag_card)

        # 底部状态通知与后备保存按钮（支持即改即存与自动化测试兼容）
        save_row = QHBoxLayout()
        self.settings_notice = label(t("set_auto_saved", "设置已自动保存"), "Muted", True)
        save_row.addWidget(self.settings_notice, 1)
        self.save_button = button(t("set_btn_save", "保存设置"), self.save_settings, "Primary")
        self.save_button.hide()
        save_row.addWidget(self.save_button)
        layout.addLayout(save_row)

    def on_theme_changed(self, index):
        theme = self.theme_input.itemData(index)
        self.store.set_setting("theme", theme)
        self.apply_theme(theme)

    def on_completion_sound_changed(self, enabled):
        self.store.set_setting("completion_sound", enabled)
        self.settings_notice.setText(t("set_auto_saved", "设置已自动保存"))

    def on_language_changed(self, index):
        lang = self.language_input.itemData(index)
        self.store.set_setting("language", lang)
        resolved = set_language(lang)
        from ..i18n import install_qt_translator
        install_qt_translator(QApplication.instance(), resolved)
        self.settings_notice.setText("语言设置已更新，重启软件后完整生效。" if resolved == "zh" else "Language updated. Full changes apply on restart.")

    def show_cookie_help(self):
        title = t("cookie_guide_title", "如何导入 YouTube Cookie")
        content = t("cookie_guide_content", "")
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setText(title)
        dialog.setInformativeText(content)
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        ok_btn = dialog.button(QMessageBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(t("btn_ok", "确定"))
        dialog.exec()

    def play_task(self, job_id):
        job = self.downloads.get(job_id)
        path = job.get("result", {}).get("path") if job else None
        if path and Path(path).is_file():
            os.startfile(path)
        else:
            QMessageBox.information(self, "VidVeya", t("hist_file_missing"))

    def reveal_task(self, job_id):
        job = self.downloads.get(job_id)
        path = job.get("result", {}).get("path") if job else None
        if path and Path(path).is_file():
            subprocess.Popen([str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "explorer.exe"),
                              "/select,", path])
        else:
            QMessageBox.information(self, "VidVeya", t("hist_file_missing"))

    def directory(self):
        return self.store.get_setting("directory", str(downloads_dir()))

    def update_folder_label(self):
        text = self.directory()
        prefix = t("dl_save_to", "保存至")
        self.folder_label.setText(f"{prefix} " + (text if len(text) < 48 else "…" + text[-45:]))
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
        inspect_finished = worker is self.inspection
        if worker is self.inspection:
            self.inspection = None
            self.parse_button.setText(t("dl_analyze", "解析视频"))
            self.parse_button.setEnabled(self.ready)
        if worker in self.workers:
            self.workers.remove(worker)
        self.update_actions()
        worker.deleteLater()
        self.maybe_finish_close()
        if inspect_finished and self._pending_analysis and not self.closing:
            self._pending_analysis = False
            self.analyze()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            self.sniff_clipboard()
        super().changeEvent(event)

    def eventFilter(self, watched, event):
        if watched is getattr(self, "url_input", None):
            if event.type() == QEvent.Type.FocusIn:
                self.sniff_clipboard()
            elif event.type() == QEvent.Type.KeyPress:
                if event.matches(QKeySequence.StandardKey.Paste):
                    try:
                        text = QApplication.clipboard().text().strip()
                        normalize_url(text)
                        is_valid = True
                    except Exception:
                        is_valid = False
                    if is_valid:
                        self.paste_smart()
                        return True
        return super().eventFilter(watched, event)

    def _on_url_text_changed(self, text):
        self.invalidate_video()
        if hasattr(self, "clear_btn"):
            self.clear_btn.setVisible(bool(text.strip()))
        if hasattr(self, "clipboard_badge"):
            if not text.strip() or text.strip() != getattr(self, "_sniffed_text", ""):
                self.clipboard_badge.hide()

    def clear_url(self):
        self._pending_analysis = False
        try:
            cb = QApplication.clipboard().text().strip()
        except Exception:
            cb = None
        self._dismissed_clipboard = cb
        self._sniffed_text = ""
        self.url_input.clear()
        self.invalidate_video()
        if hasattr(self, "clear_btn"):
            self.clear_btn.hide()
        if hasattr(self, "clipboard_badge"):
            self.clipboard_badge.hide()
        if hasattr(self, "added_actions"):
            self.added_actions.hide()

    def paste_smart(self):
        try:
            clipboard = QApplication.clipboard().text().strip()
        except Exception:
            return
        if not clipboard:
            return
        self.url_input.setText(clipboard)
        if hasattr(self, "clear_btn"):
            self.clear_btn.show()
        if hasattr(self, "clipboard_badge"):
            self.clipboard_badge.hide()
        try:
            normalize_url(clipboard)
            is_valid = True
        except UserError:
            is_valid = False
        if is_valid and self.ready:
            self.analyze()

    def sniff_clipboard(self) -> bool:
        if hasattr(self, "pages") and self.pages.currentIndex() != 0:
            return False
        has_downloads = bool(getattr(self, "downloads", None) and self.downloads.active)
        if self.video is not None or has_downloads or self.inspection is not None:
            return False
        try:
            clipboard = QApplication.clipboard().text().strip()
        except Exception:
            return False
        if not clipboard:
            return False
        if clipboard == getattr(self, "_dismissed_clipboard", None):
            return False
        try:
            normalize_url(clipboard)
            is_valid = True
        except UserError:
            is_valid = False
        if not is_valid:
            return False
        current_text = self.url_input.text().strip()
        if clipboard == current_text:
            return False
        self._dismissed_clipboard = None
        self._sniffed_text = clipboard
        self.url_input.setText(clipboard)
        if hasattr(self, "clear_btn"):
            self.clear_btn.show()
        if hasattr(self, "clipboard_badge"):
            self.clipboard_badge.setText(t("dl_clipboard_detected", "已识别剪贴板中的视频链接"))
            self.clipboard_badge.show()
        return True

    def go_to_transfers(self):
        self.show_tasks()

    def reset_for_next(self):
        try:
            cb = QApplication.clipboard().text().strip()
        except Exception:
            cb = None
        self._dismissed_clipboard = cb
        self._sniffed_text = ""
        if hasattr(self, "added_actions"):
            self.added_actions.hide()
        self.clear_url()
        self.url_input.setFocus()

    def paste(self):
        self.paste_smart()

    def clear_quality_chips(self):
        if hasattr(self, "quality_chips"):
            for chip in self.quality_chips:
                chip.deleteLater()
            self.quality_chips = []

    def rebuild_quality_chips(self):
        self.clear_quality_chips()
        if not hasattr(self, "chips_layout") or not self.visible_options:
            return
        recommended_idx = -1
        for idx, opt in enumerate(self.visible_options):
            if opt.resolution == (720 if self.quick else 1080) and opt.container == "mp4":
                recommended_idx = idx
                break
        if recommended_idx == -1 and self.visible_options:
            recommended_idx = 0

        for idx, opt in enumerate(self.visible_options):
            is_rec = (idx == recommended_idx)
            chip = QualityChipWidget(idx, opt, is_recommended=is_rec)
            chip.clicked.connect(self.on_chip_clicked)
            row = idx // 2
            col = idx % 2
            self.chips_layout.addWidget(chip, row, col)
            self.quality_chips.append(chip)
        self.sync_chip_selection()

    def on_chip_clicked(self, index: int):
        if 0 <= index < len(self.visible_options):
            self.formats.selectRow(index)
            self.sync_chip_selection()
            self.update_actions()

    def sync_chip_selection(self):
        cur = self.formats.currentRow()
        for idx, chip in enumerate(getattr(self, "quality_chips", [])):
            is_sel = (idx == cur)
            chip.setProperty("selected", "true" if is_sel else "false")
            chip.style().unpolish(chip)
            chip.style().polish(chip)
            chip.update()

    def invalidate_video(self):
        self.video = None
        self.formats.setRowCount(0)
        self.clear_quality_chips()
        if hasattr(self, "empty_placeholder"):
            self.empty_placeholder.show()
        if hasattr(self, "video_card"):
            self.video_card.hide()
        if hasattr(self, "modes_widget"):
            self.modes_widget.hide()
        if hasattr(self, "chips_widget"):
            self.chips_widget.hide()
        if hasattr(self, "format_hint"):
            self.format_hint.hide()
        self.update_actions()

    def analyze(self):
        if self.closing or not self.ready:
            if not self.ready:
                self.show_notice(t("nav_not_ready", "请先在设置中确认内置组件可用。"))
            return
        try:
            url = normalize_url(self.url_input.text())
        except UserError as error:
            self.show_notice(str(error))
            return
        if self.inspection:
            self._pending_analysis = url != self._analysis_url
            return
        self._analysis_url = url
        self.invalidate_video()
        if hasattr(self, "empty_placeholder"):
            self.empty_placeholder.hide()
        if hasattr(self, "video_card"):
            self.video_card.show()
        if hasattr(self, "clipboard_badge"):
            self.clipboard_badge.hide()
        if hasattr(self, "added_actions"):
            self.added_actions.hide()
        self.show_notice("")
        self.video_title.setText(t("dl_reading_info", "正在读取视频信息…"))
        self.video_meta.setText(t("dl_querying_meta", "正在查询可用清晰度和音轨"))
        self.thumbnail.clear()
        self.parse_button.setEnabled(False)
        self.parse_button.setText(t("dl_analyzing", "解析中…"))
        self.inspection = self.spawn({"command": "analyze", "url": url, "proxy": self.store.get_setting("proxy", ""),
                                      "use_auth": self.store.get_setting("use_auth", False)},
                                     self.analysis_result, self.analysis_error)

    def analysis_matches_input(self):
        if self.closing:
            return False
        try:
            return self._analysis_url == normalize_url(self.url_input.text())
        except UserError:
            return False

    def analysis_result(self, info):
        if self.analysis_matches_input():
            self.show_video(info)

    def analysis_error(self, message):
        if not self.analysis_matches_input():
            return
        self.show_notice(message)
        if hasattr(self, "empty_placeholder"):
            self.empty_placeholder.hide()
        if hasattr(self, "video_card"):
            self.video_card.show()
        self.video_title.setText(t("dl_error_title", "暂时无法读取视频"))
        self.video_meta.setText(t("dl_error_meta", "检查链接和网络后重新解析"))

    def show_video(self, info):
        self.video = info
        if hasattr(self, "empty_placeholder"):
            self.empty_placeholder.hide()
        if hasattr(self, "video_card"):
            self.video_card.show()
        if hasattr(self, "modes_widget"):
            self.modes_widget.show()
        if hasattr(self, "chips_widget"):
            self.chips_widget.show()
        if hasattr(self, "format_hint"):
            self.format_hint.show()
        self.video_title.setText(info["title"])
        access_map = {
            "public": t("access_public", "公开视频"),
            "unlisted": t("access_unlisted", "不公开视频"),
            "subscriber_only": t("access_premium", "频道会员专属视频"),
            "premium_only": t("access_premium", "YouTube Premium 专属视频"),
            "private": t("access_private", "私享视频"),
            "needs_auth": t("access_login_required", "需要登录账号访问"),
        }
        access = access_map.get(info.get("availability"), t("access_public", "公开视频"))
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
            values = (f"{option.label} · {option.width}×{option.height}",
                      f"{option.container.upper()} · {codec_text(option.video_codec)}",
                      f"{option.fps:g} fps" if option.fps else "—", size_text(option.estimated_bytes))
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                if column == 0:
                    item.setForeground(QColor("#CE2E37"))
                    font = QFont("Bahnschrift", 12)
                    font.setBold(True)
                    item.setFont(font)
                item.setToolTip(f"{option.width} × {option.height}\n视频：{option.video_codec}\n音频：{option.audio_codec}\n无损合并，不重新编码")
                self.formats.setItem(row, column, item)
        self.rebuild_quality_chips()
        if self.visible_options:
            target = next((index for index, item in enumerate(self.visible_options) if item.resolution == (720 if self.quick else 1080) and item.container == "mp4"), 0)
            self.formats.selectRow(target)
            self.sync_chip_selection()
        self.format_hint.setText(t("dl_hint_av1") if options else t("dl_hint_idle"))
        if options and not self.visible_options:
            self.format_hint.setText(t("dl_hint_none"))
        self.update_actions()

    def update_actions(self):
        self.sync_chip_selection()
        if hasattr(self, "download_button"):
            self.download_button.setEnabled(self.ready and self.video is not None
                                            and self.formats.currentRow() >= 0 and not self.closing)
            self.download_button.setText(t("task_add"))

    def start_download(self):
        if not self.ready or not self.video or self.closing:
            return
        row = self.formats.currentRow()
        if 0 <= row < len(self.visible_options):
            self.start_job(self.video, self.visible_options[row].to_dict())

    def start_job(self, info, option):
        if not self.ready or self.closing:
            return
        self.downloads.set_ready(self.ready)
        job, created = self.downloads.enqueue(info, option, self.directory())
        self.added_banner_label.setText(t("task_added" if created else "task_duplicate").format(title=job["title"]))
        self.added_actions.show()
        if not created:
            self.focus_task(job["id"])

    def focus_task(self, job_id):
        self.show_tasks()
        self.search_input.clear()
        self.task_list.select(job_id, focus=True)
        card = self.task_list.cards.get(job_id)
        if card:
            self.transfers_page.task_scroll.ensureWidgetVisible(card)

    def retry_task(self, job_id):
        if not self.ready or self.closing:
            return
        self.downloads.set_ready(self.ready)
        result = self.downloads.retry(job_id)
        if result:
            self.focus_task(result[0]["id"])

    def on_job_changed(self, job_id):
        job = self.downloads.get(job_id)
        if not job:
            return
        key = (job["state"], job.get("attempts"), job.get("delete_requested"), job.get("error"))
        if self._history_states.get(job_id) != key:
            self._history_states[job_id] = key
            self.refresh_history()

    def on_job_removed(self, job_id):
        self._history_states.pop(job_id, None)
        self.refresh_history()

    def on_task_completed(self, job_id):
        if self.closing:
            return
        job = self.downloads.get(job_id)
        if not job or job["state"] != "completed":
            return
        self.completion_notifier.notify(job["title"], job["option"], job.get("result", {}).get("path", ""))
        if not self.store.get_setting("completion_sound", True):
            return
        now = time.monotonic()
        if now - self._last_sound_at >= 1:
            self._last_sound_at = now
            play_completion_sound()

    def on_completion_notification_changed(self, enabled):
        self.store.set_setting("completion_notification", enabled)
        self.completion_notifier.set_enabled(enabled)

    def show_completed_tasks(self):
        if self.closing:
            return
        self.showNormal()
        self.show_tasks()
        self.raise_()
        self.activateWindow()

    def open_completed_file(self, path):
        self.open_completed_path(path, reveal=False)

    def open_completed_folder(self, path):
        self.open_completed_path(path, reveal=True)

    def open_completed_path(self, path, *, reveal):
        if self.closing:
            return
        try:
            if not path or not Path(path).is_file():
                QMessageBox.information(self, "VidVeya", t("hist_file_missing"))
                return
            if reveal:
                subprocess.Popen([str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "explorer.exe"),
                                  "/select,", path])
            else:
                os.startfile(path)
        except OSError:
            QMessageBox.information(self, "VidVeya", t("notification_open_failed"))

    def update_task_summary(self):
        summary = self.downloads.summary()
        count = summary["running"] + summary["waiting"]
        caption = t("task_summary").format(**summary)
        speed = t("task_speed").format(speed=size_text(summary["speed"]) + "/s")
        if hasattr(self, "mini_title"):
            self.mini_title.setText(caption)
        if hasattr(self, "mini_status"):
            self.mini_status.setText(speed)
        if hasattr(self, "sidebar_mini_task"):
            self.sidebar_mini_task.setVisible(count > 0)
        if hasattr(self, "mini_progress"):
            percentages = [self.downloads.progress.get(identity, {}).get("percent")
                           for identity in self.downloads.active]
            if percentages and any(value is None for value in percentages):
                self.mini_progress.setRange(0, 0)
            else:
                self.mini_progress.setRange(0, 100)
                self.mini_progress.setValue(int(sum(percentages) / len(percentages)) if percentages else 0)
        if hasattr(self, "task_summary"):
            self.task_summary.setText(caption + " · " + speed + " · " +
                                      t("task_parallel").format(count=self.downloads.max_parallel))
        if hasattr(self, "navigation") and hasattr(self, "TRANSFERS_PAGE"):
            btn = self.navigation.button(self.TRANSFERS_PAGE)
            if btn:
                btn.setText(t("nav_transfers", "⇋   传输列表") + (f"  {count}" if count else ""))
        if hasattr(self, "transfers_page"):
            self.transfers_page.update_queue_controls()
            self.transfers_page.update_badges(count, self.store.job_count())

    def confirm_delete(self, job_id):
        job = self.downloads.get(job_id)
        if not job or job.get("delete_requested"):
            return
        message = t("task_delete_confirm_active" if job["state"] in ACTIVE_STATES else "hist_confirm_delete_msg")
        reply = QMessageBox.question(self, t("hist_confirm_delete_title"), job.get("title", "") + "\n\n" + message,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.downloads.delete(job_id)

    def _update_header_labels(self):
        if not hasattr(self, "history"):
            return
        base_titles = [
            t("hist_th_video", "视频"),
            t("hist_th_res", "清晰度"),
            t("hist_th_state", "状态"),
            t("hist_th_date", "创建时间"),
        ]
        col = getattr(self, "current_sort_column", 3)
        order = getattr(self, "current_sort_order", Qt.SortOrder.DescendingOrder)
        arrow = "▲" if order == Qt.SortOrder.AscendingOrder else "▼"

        labels = []
        for index, text in enumerate(base_titles):
            if index == col:
                labels.append(f"{text}  {arrow}")
            else:
                labels.append(text)

        self.history.setHorizontalHeaderLabels(labels)

    def on_header_section_clicked(self, column: int):
        if getattr(self, "current_sort_column", None) == column:
            self.current_sort_order = (
                Qt.SortOrder.AscendingOrder
                if self.current_sort_order == Qt.SortOrder.DescendingOrder
                else Qt.SortOrder.DescendingOrder
            )
        else:
            self.current_sort_column = column
            if column in (1, 3):
                self.current_sort_order = Qt.SortOrder.DescendingOrder
            else:
                self.current_sort_order = Qt.SortOrder.AscendingOrder

        self.history.horizontalHeader().setSortIndicator(self.current_sort_column, self.current_sort_order)
        self._update_header_labels()
        self._sync_sort_combo_from_header()
        self._render_history_table()

    def _sync_sort_combo_from_header(self):
        if not hasattr(self, "sort_combo"):
            return
        mapping = {
            (3, Qt.SortOrder.DescendingOrder): "date_desc",
            (3, Qt.SortOrder.AscendingOrder): "date_asc",
            (0, Qt.SortOrder.AscendingOrder): "name_asc",
            (0, Qt.SortOrder.DescendingOrder): "name_desc",
        }
        key = mapping.get((self.current_sort_column, self.current_sort_order))
        if key:
            idx = self.sort_combo.findData(key)
            if idx >= 0:
                with QSignalBlocker(self.sort_combo):
                    self.sort_combo.setCurrentIndex(idx)

    def on_sort_changed(self):
        sort_key = self.sort_combo.currentData() if hasattr(self, "sort_combo") and self.sort_combo.count() else "date_desc"
        if sort_key == "date_desc":
            self.current_sort_column = 3
            self.current_sort_order = Qt.SortOrder.DescendingOrder
        elif sort_key == "date_asc":
            self.current_sort_column = 3
            self.current_sort_order = Qt.SortOrder.AscendingOrder
        elif sort_key == "name_asc":
            self.current_sort_column = 0
            self.current_sort_order = Qt.SortOrder.AscendingOrder
        elif sort_key == "name_desc":
            self.current_sort_column = 0
            self.current_sort_order = Qt.SortOrder.DescendingOrder

        if hasattr(self, "history"):
            self.history.horizontalHeader().setSortIndicator(self.current_sort_column, self.current_sort_order)
            self._update_header_labels()
        self._render_history_table()

    def on_search_text_changed(self, text: str):
        self._render_history_table()

    def update_history_count(self):
        total = self.store.job_count()
        if self.search_input.text().strip():
            caption = t("hist_filtered_records").format(shown=len(self.display_jobs), count=total)
        else:
            caption = t("hist_total_records").format(count=total)
            if total > len(self.history_jobs):
                caption += t("hist_shown_records").format(shown=len(self.history_jobs))
        self.history_count_label.setText(caption)

    def _get_sorted_jobs(self):
        jobs = list(self.history_jobs)
        search_kw = self.search_input.text().strip().lower() if hasattr(self, "search_input") else ""
        if search_kw:
            jobs = [
                j for j in jobs
                if search_kw in (j.get("title") or "").lower()
                or search_kw in (j.get("url") or "").lower()
                or search_kw in (j.get("id") or "").lower()
            ]
        col = getattr(self, "current_sort_column", 3)
        order = getattr(self, "current_sort_order", Qt.SortOrder.DescendingOrder)
        is_reverse = (order == Qt.SortOrder.DescendingOrder)

        if col == 0:
            jobs.sort(key=lambda j: (j.get("title") or "").lower(), reverse=is_reverse)
        elif col == 1:
            def parse_res(j):
                res_str = str(j.get("option", {}).get("resolution", ""))
                digits = "".join(filter(str.isdigit, res_str))
                return int(digits) if digits else 0
            jobs.sort(key=parse_res, reverse=is_reverse)
        elif col == 2:
            state_priority = {
                "downloading": 1, "merging": 2, "verifying": 3, "starting": 4,
                "completed": 5, "failed": 6, "cancelled": 7, "interrupted": 8, "queued": -2, "retry_wait": -1,
            }
            jobs.sort(key=lambda j: (state_priority.get(j.get("state", ""), 99), (j.get("title") or "").lower()), reverse=is_reverse)
        elif col == 3:
            jobs.sort(key=lambda j: j.get("created", ""), reverse=is_reverse)
        else:
            jobs.sort(key=lambda j: j.get("created", ""), reverse=True)
        return jobs

    def refresh_history(self):
        self.history_jobs = self.store.jobs()
        if hasattr(self, "clear_history_button"):
            self.clear_history_button.setEnabled(self.store.has_finished_jobs())
        if hasattr(self, "transfers_page"):
            summary = self.downloads.summary() if hasattr(self, "downloads") else {"running": 0, "waiting": 0}
            active_count = summary["running"] + summary["waiting"]
            self.transfers_page.update_badges(active_count, self.store.job_count())
        self._render_history_table()

    def _render_history_table(self):
        self._update_header_labels()
        selected = self.selected_job()
        selected_id = selected["id"] if selected else None
        # 刷新或排序后按任务 ID 恢复选择，避免同一行变成另一条记录。
        with QSignalBlocker(self.history):
            self.display_jobs = self._get_sorted_jobs()
            self.history.setRowCount(0)
            self.history.setRowCount(len(self.display_jobs))
            for row, job in enumerate(self.display_jobs):
                state = job.get("state", "")
                state_text = t(f"state_{state}", STATE_LABELS.get(state, state))
                created_str = format_local_datetime(job.get("created", ""))

                opt = job.get("option", {})
                res = opt.get("resolution", "")
                container = opt.get("container", "").upper()
                format_spec = f"{res}P · {container}" if res else container

                title_item = QTableWidgetItem(job.get("title", ""))
                title_item.setToolTip(job.get("title", ""))
                self.history.setItem(row, 0, title_item)

                res_item = QTableWidgetItem(format_spec)
                res_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.history.setItem(row, 1, res_item)

                if state == "completed":
                    state_display = f"✓  {state_text}"
                    color = QColor("#10B981")
                elif state == "failed":
                    state_display = f"✕  {state_text}"
                    color = QColor("#EF4444")
                elif state in ("cancelled", "interrupted"):
                    state_display = f"—  {state_text}"
                    color = QColor("#6B7280")
                else:
                    state_display = f"●  {state_text}"
                    color = QColor("#0078D4")

                state_item = QTableWidgetItem(state_display)
                state_item.setForeground(color)
                state_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.history.setItem(row, 2, state_item)

                date_item = QTableWidgetItem(created_str)
                date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.history.setItem(row, 3, date_item)
                if job["id"] == selected_id:
                    self.history.selectRow(row)

        if not self.display_jobs:
            search_kw = self.search_input.text().strip() if hasattr(self, "search_input") else ""
            self.history_detail.setText(t("hist_filter_empty", "未找到匹配的记录") if search_kw else t("hist_empty", "尚无下载记录。"))
        else:
            self.history_detail.setText(t("hist_select_hint", "选择记录查看详情。"))
        self.select_history()
        self.update_history_count()

    def selected_job(self):
        row = self.history.currentRow()
        jobs = getattr(self, "display_jobs", self.history_jobs)
        return jobs[row] if 0 <= row < len(jobs) else None

    def select_history(self):
        if not hasattr(self, "reveal_button"):
            return
        job = self.selected_job()
        has_file = bool(job and job.get("result", {}).get("path"))
        self.reveal_button.setEnabled(has_file)
        if hasattr(self, "play_history_button"):
            self.play_history_button.setEnabled(has_file)
        if hasattr(self, "delete_history_button"):
            self.delete_history_button.setEnabled(bool(job and not job.get("delete_requested") and not self.closing))
        self.retry_button.setEnabled(bool(job and job["state"] in {"completed", "failed", "cancelled", "interrupted"} and not self.closing))
        if job:
            self.history_detail.setText(job.get("error") or job.get("result", {}).get("path", t("hist_in_progress", "任务正在进行")))
        elif not self.display_jobs:
            search_kw = self.search_input.text().strip() if hasattr(self, "search_input") else ""
            self.history_detail.setText(t("hist_filter_empty", "未找到匹配的记录") if search_kw else t("hist_empty", "尚无下载记录。"))

    def reveal_selected(self):
        job = self.selected_job()
        path = Path(job.get("result", {}).get("path", "")) if job else None
        if path and path.is_file():
            subprocess.Popen([str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "explorer.exe"), "/select,", str(path)])
        else:
            self.history_detail.setText(t("hist_file_missing", "文件已被移动或删除。"))

    def play_selected_history(self):
        job = self.selected_job()
        path = Path(job.get("result", {}).get("path", "")) if job else None
        if path and path.is_file():
            os.startfile(path)
        else:
            self.history_detail.setText(t("hist_file_missing", "文件已被移动或删除。"))

    def retry_selected(self):
        job = self.selected_job()
        if job:
            self.retry_task(job["id"])

    def delete_selected(self):
        job = self.selected_job()
        if job and not job.get("delete_requested") and not self.closing:
            self.confirm_delete(job["id"])

    def clear_all_history(self):
        if not self.store.has_finished_jobs():
            return
        reply = QMessageBox.question(
            self,
            t("hist_confirm_clear_title", "清空下载记录"),
            t("hist_confirm_clear_msg", "确定要清空已结束任务的记录吗？\n正在进行的任务和已下载的视频文件会保留。"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.store.clear_jobs()
            self.downloads.forget_finished()
            self.refresh_history()

    def show_history_context_menu(self, pos):
        item = self.history.itemAt(pos)
        if not item:
            return
        row = item.row()
        self.history.selectRow(row)
        job = self.selected_job()
        if not job:
            return

        menu = QMenu(self)
        path = Path(job.get("result", {}).get("path", "")) if job.get("result") else None
        has_file = bool(path and path.is_file())

        play_act = menu.addAction(t("hist_menu_play", "▶  播放视频"))
        play_act.setEnabled(has_file)
        play_act.triggered.connect(lambda: self.play_task(job["id"]))

        reveal_act = menu.addAction(t("hist_menu_reveal", "📂  打开所在文件夹"))
        reveal_act.setEnabled(has_file)
        reveal_act.triggered.connect(lambda: self.reveal_task(job["id"]))

        retry_act = menu.addAction(t("hist_menu_retry", "↺  重新下载"))
        retry_act.setEnabled(bool(job["state"] in {"completed", "failed", "cancelled", "interrupted"} and not self.closing))
        retry_act.triggered.connect(lambda: self.retry_task(job["id"]))

        menu.addSeparator()

        copy_url_act = menu.addAction(t("hist_menu_copy_url", "🔗  复制视频链接"))
        copy_url_act.triggered.connect(lambda: QApplication.clipboard().setText(job.get("url", "")))

        copy_title_act = menu.addAction(t("hist_menu_copy_title", "📋  复制视频标题"))
        copy_title_act.triggered.connect(lambda: QApplication.clipboard().setText(job.get("title", "")))

        menu.addSeparator()

        delete_act = menu.addAction(t("hist_menu_delete", "🗑  删除此记录 (Del)"))
        delete_act.setEnabled(bool(job and not job.get("delete_requested") and not self.closing))
        delete_act.setShortcut(QKeySequence(Qt.Key.Key_Delete))
        delete_act.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        delete_act.triggered.connect(lambda: self.confirm_delete(job["id"]))

        try:
            menu.exec(self.history.viewport().mapToGlobal(pos))
        finally:
            menu.deleteLater()

    def on_history_double_clicked(self, item):
        job = self.selected_job()
        if not job:
            return
        path = Path(job.get("result", {}).get("path", "")) if job.get("result") else None
        if path and path.is_file():
            self.play_selected_history()
        elif not self.closing and job.get("state") in {"completed", "failed", "cancelled", "interrupted"}:
            self.retry_selected()

    def choose_directory(self):
        chosen = QFileDialog.getExistingDirectory(self, t("select_save_dir", "选择保存目录"), self.directory_input.text())
        if chosen:
            self.directory_input.setText(chosen)
            self.auto_save()

    def auto_save(self):
        try:
            proxy = validate_proxy(self.proxy_input.text()) if hasattr(self, "proxy_input") else ""
            if hasattr(self, "directory_input") and self.directory_input.text().strip():
                directory = Path(self.directory_input.text()).expanduser()
                if directory.is_absolute():
                    directory.mkdir(parents=True, exist_ok=True)
                    self.store.set_setting("directory", str(directory.resolve()))
            if hasattr(self, "proxy_input"):
                self.store.set_setting("proxy", proxy)
            if hasattr(self, "close_action_input") and self.close_action_input.currentData():
                self.store.set_setting("close_action", self.close_action_input.currentData())
            if hasattr(self, "close_prompt_input"):
                self.store.set_setting("confirm_close", self.close_prompt_input.isChecked())
            self.update_folder_label()
            if hasattr(self, "settings_notice"):
                self.settings_notice.setText(t("set_auto_saved", "设置已自动保存"))
        except (UserError, OSError) as error:
            if hasattr(self, "settings_notice"):
                self.settings_notice.setText(str(error))

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
            self.store.set_setting("close_action", self.close_action_input.currentData())
            self.store.set_setting("confirm_close", self.close_prompt_input.isChecked())
            self.update_folder_label()
            self.settings_notice.setText(t("set_save_success", "已保存。设置立即生效，下载设置用于下次下载。"))
        except (UserError, OSError) as error:
            self.settings_notice.setText(str(error))

    def toggle_auth(self, checked):
        if checked and not vault_path().exists():
            self.auth_enabled.setChecked(False)
            self.auth_notice.setText("请先导入有观看权限账号的 YouTube Cookie 文件。")
            return
        self.store.set_setting("use_auth", checked)

    def import_session(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            t("select_cookie_file", "选择 Cookie 文件"),
            "",
            t("file_filter_text", "文本文件 (*.txt);;所有文件 (*.*)"),
        )
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
        self.check_button.setText(t("dl_analyzing", "检查中…"))
        self.parse_button.setEnabled(False)
        self.spawn({"command": "diagnostics"}, self.components_checked, self.component_error)

    def components_checked(self, result):
        self.component_table.setRowCount(len(result))
        for row, (name, status) in enumerate(result.items()):
            self.component_table.setItem(row, 0, QTableWidgetItem(name))
            status_txt = (t("set_comp_ok", "可用") + "  ·  " if status["ok"] else t("set_comp_error", "异常") + "  ·  ") + status["version"]
            item = QTableWidgetItem(status_txt)
            item.setToolTip(item.text())
            item.setForeground(QColor("#10B981" if status["ok"] else "#E53935"))
            self.component_table.setItem(row, 1, item)
        self.ready = bool(result) and all(status["ok"] for status in result.values())
        self.downloads.set_ready(self.ready)
        self.update_task_summary()
        self.health_label.setText(t("nav_ready", "●  下载组件就绪") if self.ready else t("nav_not_ready", "●  请检查内置组件"))
        self.check_button.setEnabled(True)
        self.check_button.setText(t("set_btn_recheck", "重新检查"))
        self.parse_button.setEnabled(self.ready and not self.inspection)
        if not self.ready:
            self.show_notice(t("nav_not_ready", "部分内置组件不可用，请在设置中查看详情，或重新完整安装。"))
        self.update_actions()

    def component_error(self, message):
        self.ready = False
        self.downloads.set_ready(False)
        self.health_label.setText(t("nav_check_failed", "●  组件检查失败"))
        self.check_button.setEnabled(True)
        self.check_button.setText(t("set_btn_recheck", "重新检查"))
        self.show_notice(message)
        self.update_actions()

    def request_exit(self):
        """显式退出不受窗口关闭偏好影响，仍确认正在运行的下载。"""
        self._exit_requested = True
        try:
            return self.close()
        finally:
            self._exit_requested = False

    def ask_close_action(self, action):
        dialog = QMessageBox(self)
        dialog.setWindowTitle(t("dialog_close_title", "关闭 VidVeya"))
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setText(
            t("dialog_close_minimize_msg", "关闭窗口后将最小化到任务栏，下载会继续。") if action == "minimize"
            else t("dialog_close_exit_msg", "关闭窗口后将退出 VidVeya。")
        )
        dialog.setInformativeText(t("dialog_close_text", "请选择关闭窗口时的操作："))
        minimize = dialog.addButton(t("btn_minimize", "最小化"), QMessageBox.ButtonRole.AcceptRole)
        quit_button = dialog.addButton(t("btn_exit", "退出软件"), QMessageBox.ButtonRole.DestructiveRole)
        cancel = dialog.addButton(t("btn_cancel", "取消"), QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(quit_button if action == "exit" else minimize)
        dialog.setEscapeButton(cancel)
        remember = QCheckBox(t("btn_remember", "记住我的选择，不再提示"), dialog)
        dialog.setCheckBox(remember)
        dialog.exec()
        chosen = dialog.clickedButton()
        selected = "minimize" if chosen is minimize else "exit" if chosen is quit_button else None
        result = selected, remember.isChecked()
        dialog.deleteLater()
        return result

    def closeEvent(self, event):
        if self.closing:
            if self.downloads.active or self.workers:
                event.ignore()
            else:
                event.accept()
            return
        action = "exit" if self._exit_requested else self.store.get_setting("close_action", "minimize")
        remember = False
        if not self._exit_requested and self.store.get_setting("confirm_close", True):
            action, remember = self.ask_close_action(action)
            if action is None:
                event.ignore()
                return
        if action != "exit":
            if remember:
                self.remember_close_action("minimize")
            event.ignore()
            self.showMinimized()
            return
        counts = self.downloads.summary()
        if counts["running"] or counts["waiting"]:
            answer = QMessageBox.question(
                self,
                t("dialog_exit_confirm_title", "确认退出"),
                t("task_exit_confirm").format(**counts),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        if remember:
            self.remember_close_action("exit")
        self.closing = True
        self.completion_notifier.shutdown()
        self.centralWidget().setEnabled(False)
        self.downloads.shutdown()
        for worker in list(self.workers):
            worker.cancel()
        if self.thumbnail_reply:
            self.thumbnail_reply.abort()
        if self.downloads.active or self.workers:
            event.ignore()
        else:
            event.accept()

    def maybe_finish_close(self):
        if self.closing and not self.downloads.active and not self.workers:
            QTimer.singleShot(0, self.close)

    def remember_close_action(self, action):
        self.store.set_setting("close_action", action)
        self.store.set_setting("confirm_close", False)
        self.close_action_input.setCurrentIndex(self.close_action_input.findData(action))
        self.close_prompt_input.setChecked(False)
