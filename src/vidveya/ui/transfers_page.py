import os
from pathlib import Path
import subprocess

from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QComboBox, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListView, QMenu, QMessageBox, QPushButton,
    QScrollArea, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from ..i18n import t
from ..models import ACTIVE_STATES
from .formatting import duration_text, size_text
from .task_list import TaskList


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


def label(text: str = "", role: str = "", wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if role:
        widget.setObjectName(role)
    widget.setWordWrap(wrap)
    return widget


def button(text: str, handler=None, role: str = "") -> QPushButton:
    widget = QPushButton(text)
    if role:
        widget.setObjectName(role)
    if handler:
        widget.clicked.connect(handler)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


class TransfersPage(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        self.setObjectName("Page")
        self._init_ui()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(32, 24, 32, 24)
        root_layout.setSpacing(16)

        # 1. 顶部标题区域
        heading_box = QVBoxLayout()
        heading_box.setSpacing(4)
        heading_box.addWidget(label(t("transfers_heading", "传输列表"), "Heading"))
        heading_box.addWidget(label(t("transfers_subtitle", "统一查看进行中的下载任务与已完成的历史记录。"), "Muted", True))
        root_layout.addLayout(heading_box)

        # 2. 顶部工具栏：分段控制器 + 实时检索 + 批量操作
        toolbar = QHBoxLayout()
        toolbar.setSpacing(14)

        # 分段控制器
        self.segmented_control = QFrame()
        self.segmented_control.setObjectName("SegmentedControl")
        seg_layout = QHBoxLayout(self.segmented_control)
        seg_layout.setContentsMargins(4, 4, 4, 4)
        seg_layout.setSpacing(4)

        self.btn_active = QPushButton(t("transfers_tab_active", "进行中") + " (0)")
        self.btn_active.setObjectName("SegmentBtn")
        self.btn_active.setCheckable(True)
        self.btn_active.setChecked(True)

        self.btn_history = QPushButton(t("transfers_tab_history", "已完成") + " (0)")
        self.btn_history.setObjectName("SegmentBtn")
        self.btn_history.setCheckable(True)

        self.seg_group = QButtonGroup(self)
        self.seg_group.setExclusive(True)
        self.seg_group.addButton(self.btn_active, 0)
        self.seg_group.addButton(self.btn_history, 1)
        self.seg_group.idClicked.connect(self._on_segment_changed)

        seg_layout.addWidget(self.btn_active)
        seg_layout.addWidget(self.btn_history)
        toolbar.addWidget(self.segmented_control)

        # 实时检索框
        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText(t("transfers_search_placeholder", "搜索任务或视频标题…"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(260)
        self.search_input.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_input)

        toolbar.addStretch()

        # 批量操作栏（根据当前选中的分段展示）
        self.actions_stack = QStackedWidget()

        # 进行中批量操作
        active_actions = QWidget()
        act_layout = QHBoxLayout(active_actions)
        act_layout.setContentsMargins(0, 0, 0, 0)
        act_layout.setSpacing(8)
        self.resume_all_btn = button(t("transfers_resume_all", "全部继续"), self._resume_all)
        self.resume_all_btn.hide()
        self.pause_all_btn = button(t("transfers_pause_all", "全部暂停"), self._pause_all)
        act_layout.addWidget(self.resume_all_btn)
        act_layout.addWidget(self.pause_all_btn)
        self.actions_stack.addWidget(active_actions)

        # 已完成批量操作
        history_actions = QWidget()
        hist_act_layout = QHBoxLayout(history_actions)
        hist_act_layout.setContentsMargins(0, 0, 0, 0)
        hist_act_layout.setSpacing(8)
        self.clear_history_button = button(t("transfers_clear_history", "清空已完成记录"), self._clear_history, "DangerSecondary")
        self.clear_history_button.setEnabled(False)
        hist_act_layout.addWidget(self.clear_history_button)
        self.actions_stack.addWidget(history_actions)

        toolbar.addWidget(self.actions_stack)
        root_layout.addLayout(toolbar)

        # 3. 核心内容区域 (QStackedWidget)
        self.content_stack = QStackedWidget()

        # Page 0: 进行中任务列表
        active_page = QWidget()
        active_layout = QVBoxLayout(active_page)
        active_layout.setContentsMargins(0, 0, 0, 0)
        active_layout.setSpacing(10)

        self.task_scroll = QScrollArea()
        self.task_scroll.setWidgetResizable(True)
        self.task_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.task_list = TaskList(self.window.downloads, self)
        self.task_scroll.setWidget(self.task_list)
        active_layout.addWidget(self.task_scroll, 1)

        self.active_empty = QFrame()
        self.active_empty.setObjectName("SubCard")
        empty_layout = QVBoxLayout(self.active_empty)
        empty_layout.setContentsMargins(32, 36, 32, 36)
        empty_layout.setSpacing(10)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon = label("📥")
        empty_icon.setStyleSheet("font-size: 36px; background: transparent;")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)
        empty_title = label(t("transfers_empty_active", "暂无正在进行的下载任务"), "Subheading")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_title)
        empty_sub = label(t("task_empty", "添加视频链接后，任务将在此处极速下载"), "Muted")
        empty_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_sub)
        self.active_empty.hide()
        active_layout.addWidget(self.active_empty)

        self.content_stack.addWidget(active_page)

        # Page 1: 已完成历史记录
        history_page = QWidget()
        history_layout = QVBoxLayout(history_page)
        history_layout.setContentsMargins(0, 0, 0, 0)
        history_layout.setSpacing(10)

        # 隐藏的 sort_combo 供向下兼容
        self.sort_combo = combo_box("排序方式")
        self.sort_combo.addItem(t("hist_sort_date_desc", "创建时间 (最新)"), "date_desc")
        self.sort_combo.addItem(t("hist_sort_date_asc", "创建时间 (最早)"), "date_asc")
        self.sort_combo.addItem(t("hist_sort_name_asc", "视频名称 (A-Z)"), "name_asc")
        self.sort_combo.addItem(t("hist_sort_name_desc", "视频名称 (Z-A)"), "name_desc")
        self.sort_combo.currentIndexChanged.connect(self.window.on_sort_changed)
        self.sort_combo.hide()
        history_layout.addWidget(self.sort_combo)

        # 历史记录表格
        self.history = QTableWidget(0, 4)
        header = self.history.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for index in range(1, 4):
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.current_sort_column = 3
        self.current_sort_order = Qt.SortOrder.DescendingOrder
        self.window.current_sort_column = 3
        self.window.current_sort_order = Qt.SortOrder.DescendingOrder
        header.setSortIndicator(self.current_sort_column, self.current_sort_order)
        header.sectionClicked.connect(self.window.on_header_section_clicked)

        self.history.verticalHeader().hide()
        self.history.verticalHeader().setDefaultSectionSize(46)
        self.history.setShowGrid(False)
        self.history.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history.itemSelectionChanged.connect(self.window.select_history)
        self.history.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history.customContextMenuRequested.connect(self.window.show_history_context_menu)
        self.history.itemDoubleClicked.connect(self.window.on_history_double_clicked)

        self.history_delete_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self.history)
        self.history_delete_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.history_delete_shortcut.setAutoRepeat(False)
        self.history_delete_shortcut.activated.connect(self.window.delete_selected)

        history_layout.addWidget(self.history, 1)

        self.history_detail = label(t("hist_empty", "尚无下载记录。"), "Muted", True)
        history_layout.addWidget(self.history_detail)

        # 保持向后兼容操作按钮（隐藏）
        self.compat_actions = QWidget()
        compat_layout = QHBoxLayout(self.compat_actions)
        self.reveal_button = button(t("hist_btn_reveal", "打开文件夹"), self.window.reveal_selected)
        self.play_history_button = button(t("hist_btn_play", "播放视频"), self.window.play_selected_history)
        self.retry_button = button(t("hist_btn_retry", "重新下载"), self.window.retry_selected)
        self.delete_history_button = button(t("hist_btn_delete", "删除记录"), self.window.delete_selected, "DangerSecondary")
        for btn in (self.reveal_button, self.play_history_button, self.retry_button, self.delete_history_button):
            btn.setEnabled(False)
            compat_layout.addWidget(btn)
        self.compat_actions.hide()
        history_layout.addWidget(self.compat_actions)

        self.content_stack.addWidget(history_page)
        root_layout.addWidget(self.content_stack, 1)

        # 任务汇总状态文字（向后兼容）
        self.task_summary = label("", "Status", True)
        self.task_summary.hide()
        root_layout.addWidget(self.task_summary)

    def _on_segment_changed(self, tab_id: int):
        if self.content_stack.currentIndex() == tab_id:
            return
        self.content_stack.setCurrentIndex(tab_id)
        self.actions_stack.setCurrentIndex(tab_id)
        self._on_search_changed(self.search_input.text())

    def _on_search_changed(self, text: str):
        if self.content_stack.currentIndex() == 0:
            self.task_list.set_filter(text)
        else:
            self.window.on_search_text_changed(text)

    def switch_to_active(self):
        if self.content_stack.currentIndex() == 0 and self.btn_active.isChecked():
            return
        self.btn_active.setChecked(True)
        self._on_segment_changed(0)

    def switch_to_history(self):
        if self.content_stack.currentIndex() == 1 and self.btn_history.isChecked():
            return
        self.btn_history.setChecked(True)
        self._on_segment_changed(1)

    def update_badges(self, active_count: int, history_count: int):
        self.btn_active.setText(f"{t('transfers_tab_active', '进行中')}  {active_count}")
        self.btn_history.setText(f"{t('transfers_tab_history', '已完成')}  {history_count}")
        self.active_empty.setVisible(active_count == 0)
        self.task_scroll.setVisible(active_count > 0)

    def _pause_all(self):
        self.window.downloads.pause()

    def _resume_all(self):
        self.window.downloads.resume()

    def _clear_history(self):
        self.window.clear_all_history()
