"""Modern Windows 11 Fluent theme stylesheets for VidVeya."""
import sys

if sys.platform == "win32":
    import winreg
else:
    winreg = None


LIGHT_THEME = {
    "bg_app": "#F8FAFC",
    "bg_surface": "#FFFFFF",
    "bg_subtle": "#F1F5F9",
    "bg_hover": "#F1F5F9",
    "border": "#E2E8F0",
    "border_strong": "#CBD5E1",
    "border_light": "#EDF2F7",
    "border_focus": "#E53935",
    "text_main": "#0F172A",
    "text_muted": "#64748B",
    "text_faint": "#94A3B8",
    "accent": "#E53935",
    "accent_hover": "#D32F2F",
    "accent_pressed": "#B71C1C",
    "accent_tint": "#FEECEE",
    "accent_tint_border": "#FCA5A5",
    "accent_disabled": "#FCA5A5",
    "sidebar_bg": "#FFFFFF",
    "sidebar_border": "#E2E8F0",
    "table_header_bg": "#F8FAFC",
    "progress_bg": "#E2E8F0",
    "progress_chunk": "#E53935",
    "notice_bg": "#FEECEE",
    "notice_text": "#B71C1C",
    "badge_bg": "#F1F5F9",
    "badge_text": "#334155",
    "badge_green_bg": "#ECFDF5",
    "badge_green_text": "#059669",
    "danger": "#DC2626",
    "danger_hover": "#B91C1C",
    "danger_bg": "#FEE2E2",
    "danger_border": "#FCA5A5",
}

DARK_THEME = {
    "bg_app": "#0F1117",
    "bg_surface": "#181B22",
    "bg_subtle": "#212631",
    "bg_hover": "#262C38",
    "border": "#2D3340",
    "border_strong": "#3D4453",
    "border_light": "#222731",
    "border_focus": "#EF4444",
    "text_main": "#F8FAFC",
    "text_muted": "#94A3B8",
    "text_faint": "#64748B",
    "accent": "#E53935",
    "accent_hover": "#EF4444",
    "accent_pressed": "#DC2626",
    "accent_tint": "#381A1C",
    "accent_tint_border": "#7F1D1D",
    "accent_disabled": "#7F1D1D",
    "sidebar_bg": "#13161C",
    "sidebar_border": "#222732",
    "table_header_bg": "#181B22",
    "progress_bg": "#2A303C",
    "progress_chunk": "#EF4444",
    "notice_bg": "#381A1C",
    "notice_text": "#FCA5A5",
    "badge_bg": "#262C38",
    "badge_text": "#CBD5E1",
    "badge_green_bg": "#064E3B",
    "badge_green_text": "#34D399",
    "danger": "#F87171",
    "danger_hover": "#EF4444",
    "danger_bg": "#3B181A",
    "danger_border": "#7F1D1D",
}


def detect_system_theme() -> str:
    """检测 Windows 系统主题，返回 'dark' 或 'light'。"""
    if winreg is not None:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return "light" if value != 0 else "dark"
        except Exception:
            pass
    return "light"


def resolve_theme(theme: str = "system") -> str:
    """解析实际主题模式（'light' 或 'dark'）。"""
    if theme == "system" or not theme:
        return detect_system_theme()
    return "dark" if theme == "dark" else "light"


def get_theme_stylesheet(theme: str = "system") -> str:
    actual_theme = resolve_theme(theme)
    tokens = DARK_THEME if actual_theme == "dark" else LIGHT_THEME
    return f"""
QMainWindow, QWidget#Workspace, QWidget#Page {{
    background: {tokens['bg_app']};
}}
QWidget {{
    font-family: 'Segoe UI', 'Microsoft YaHei UI', -apple-system, sans-serif;
    font-size: 14px;
    color: {tokens['text_main']};
}}
QLabel {{
    background: transparent;
}}
QLabel#Brand {{
    font-size: 20px;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: {tokens['accent']};
}}
QLabel#Eyebrow {{
    font-size: 11px;
    font-weight: 700;
    color: {tokens['text_muted']};
    letter-spacing: 0.8px;
}}
QLabel#Heading {{
    font-size: 22px;
    font-weight: 700;
    color: {tokens['text_main']};
    letter-spacing: -0.4px;
}}
QLabel#Subheading {{
    font-size: 15px;
    font-weight: 600;
    color: {tokens['text_main']};
}}
QLabel#Subtitle {{
    font-size: 13px;
    color: {tokens['text_muted']};
}}
QLabel#Muted {{
    color: {tokens['text_muted']};
    font-size: 13px;
}}
QLabel#Status {{
    color: {tokens['text_muted']};
    font-size: 12px;
}}
QLabel#Badge {{
    background: {tokens['badge_bg']};
    color: {tokens['badge_text']};
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 12px;
    font-weight: 600;
}}
QLabel#BadgeSuccess {{
    background: {tokens['badge_green_bg']};
    color: {tokens['badge_green_text']};
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 12px;
    font-weight: 600;
}}
QFrame#Sidebar {{
    background: {tokens['sidebar_bg']};
    border-right: 1px solid {tokens['sidebar_border']};
}}
QFrame#Card {{
    background: {tokens['bg_surface']};
    border: 1px solid {tokens['border']};
    border-radius: 12px;
}}
QFrame#Card QLabel {{
    background: transparent;
}}
QFrame#SubCard {{
    background: {tokens['bg_subtle']};
    border: 1px solid {tokens['border_light']};
    border-radius: 8px;
}}
QFrame#SubCard QLabel {{
    background: transparent;
}}
QPushButton {{
    background: {tokens['bg_surface']};
    color: {tokens['text_main']};
    border: 1px solid {tokens['border']};
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {tokens['bg_hover']};
    border-color: {tokens['border_strong']};
}}
QPushButton:pressed {{
    background: {tokens['border']};
}}
QPushButton:focus {{
    border: 2px solid {tokens['border_focus']};
    padding: 7px 15px;
}}
QPushButton:disabled {{
    color: {tokens['text_faint']};
    background: {tokens['bg_subtle']};
    border-color: {tokens['border']};
}}
QPushButton#Primary {{
    color: #FFFFFF;
    background: {tokens['accent']};
    border-color: {tokens['accent']};
}}
QPushButton#Primary:hover {{
    background: {tokens['accent_hover']};
    border-color: {tokens['accent_hover']};
}}
QPushButton#Primary:pressed {{
    background: {tokens['accent_pressed']};
    border-color: {tokens['accent_pressed']};
}}
QPushButton#Primary:disabled {{
    background: {tokens['accent_disabled']};
    border-color: {tokens['accent_disabled']};
    color: #FFFFFF;
}}
QPushButton#Navigation {{
    text-align: left;
    border: 1px solid transparent;
    border-radius: 8px;
    background: transparent;
    color: {tokens['text_muted']};
    padding: 10px 14px;
    font-weight: 500;
}}
QPushButton#Navigation:hover {{
    background: {tokens['bg_hover']};
    color: {tokens['text_main']};
}}
QPushButton#Navigation:checked {{
    color: {tokens['accent']};
    background: {tokens['accent_tint']};
    font-weight: 700;
    border-color: {tokens['accent_tint_border']};
}}
QPushButton#ExitButton {{
    text-align: left;
    border: 1px solid transparent;
    border-radius: 8px;
    background: transparent;
    color: {tokens['text_muted']};
    padding: 9px 14px;
    font-weight: 500;
    font-size: 13px;
}}
QPushButton#ExitButton:hover {{
    background: {tokens['danger_bg']};
    color: {tokens['danger']};
    border: 1px solid {tokens['danger_border']};
    font-weight: 600;
}}
QPushButton#ExitButton:pressed {{
    background: {tokens['danger_border']};
    color: {tokens['danger']};
}}
QPushButton#Danger {{
    background: {tokens['danger']};
    color: #FFFFFF;
    border: 1px solid {tokens['danger']};
    border-radius: 8px;
    padding: 7px 16px;
    font-weight: 600;
}}
QPushButton#Danger:hover {{
    background: {tokens['danger_hover']};
    border-color: {tokens['danger_hover']};
}}
QPushButton#DangerSecondary {{
    background: {tokens['bg_surface']};
    color: {tokens['danger']};
    border: 1px solid {tokens['danger_border']};
    border-radius: 8px;
    padding: 6px 14px;
    font-weight: 500;
    font-size: 13px;
}}
QPushButton#DangerSecondary:hover {{
    background: {tokens['danger_bg']};
    border-color: {tokens['danger']};
}}
QPushButton#Mode {{
    padding: 7px 18px;
    border-radius: 8px;
    font-size: 13px;
}}
QPushButton#Mode:checked {{
    color: {tokens['accent']};
    background: {tokens['accent_tint']};
    border-color: {tokens['accent_tint_border']};
    font-weight: 700;
}}
QLineEdit {{
    background: {tokens['bg_surface']};
    color: {tokens['text_main']};
    border: 1px solid {tokens['border']};
    border-radius: 8px;
    padding: 9px 12px;
    selection-background-color: {tokens['accent']};
}}
QLineEdit:focus {{
    border: 2px solid {tokens['border_focus']};
    padding: 8px 11px;
}}
QLineEdit:disabled {{
    background: {tokens['bg_subtle']};
    color: {tokens['text_faint']};
}}
QComboBox {{
    background: {tokens['bg_surface']};
    color: {tokens['text_main']};
    border: 1px solid {tokens['border']};
    border-radius: 8px;
    padding: 7px 12px;
    min-height: 20px;
}}
QComboBox:hover {{
    border-color: {tokens['border_strong']};
}}
QComboBox:focus {{
    border: 2px solid {tokens['border_focus']};
    padding: 6px 11px;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border-left: 0;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}}
QComboBox::down-arrow {{
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {tokens['text_muted']};
    margin-right: 8px;
}}
QComboBox::down-arrow:hover {{
    border-top-color: {tokens['accent']};
}}
QComboBox QAbstractItemView {{
    outline: 0;
    background: {tokens['bg_surface']};
    color: {tokens['text_main']};
    border: 1px solid {tokens['border']};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {tokens['accent_tint']};
    selection-color: {tokens['accent']};
}}
QComboBox QAbstractItemView::item {{
    min-height: 32px;
    padding: 4px 10px;
    border-radius: 6px;
    color: {tokens['text_main']};
}}
QComboBox QAbstractItemView::item:hover {{
    background: {tokens['bg_hover']};
    color: {tokens['text_main']};
}}
QComboBox QAbstractItemView::item:selected {{
    background: {tokens['accent_tint']};
    color: {tokens['accent']};
    font-weight: 600;
}}
QMenu {{
    background: {tokens['bg_surface']};
    color: {tokens['text_main']};
    border: 1px solid {tokens['border']};
    border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{
    padding: 8px 24px 8px 12px;
    border-radius: 6px;
    font-size: 13px;
    color: {tokens['text_main']};
}}
QMenu::item:selected {{
    background: {tokens['bg_hover']};
    color: {tokens['text_main']};
}}
QMenu::item:disabled {{
    color: {tokens['text_faint']};
    background: transparent;
}}
QMenu::separator {{
    height: 1px;
    background: {tokens['border_light']};
    margin: 4px 6px;
}}
QTableWidget {{
    background: {tokens['bg_surface']};
    color: {tokens['text_main']};
    border: 1px solid {tokens['border']};
    border-radius: 10px;
    gridline-color: {tokens['border_light']};
    selection-background-color: {tokens['accent_tint']};
    selection-color: {tokens['text_main']};
}}
QTableWidget::item {{
    padding: 8px;
    border: 0;
}}
QTableWidget::item:selected {{
    background: {tokens['accent_tint']};
    color: {tokens['text_main']};
}}
QHeaderView::section {{
    background: {tokens['table_header_bg']};
    color: {tokens['text_muted']};
    padding: 10px 8px;
    border: 0;
    border-bottom: 1px solid {tokens['border']};
    font-weight: 600;
    font-size: 13px;
}}
QHeaderView::section:hover {{
    background: {tokens['bg_hover']};
    color: {tokens['text_main']};
}}
QHeaderView::up-arrow {{
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {tokens['accent']};
    margin-right: 6px;
    margin-bottom: 2px;
}}
QHeaderView::down-arrow {{
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {tokens['accent']};
    margin-right: 6px;
    margin-top: 2px;
}}
QProgressBar {{
    border: 0;
    border-radius: 6px;
    background: {tokens['progress_bg']};
    text-align: center;
}}
QProgressBar::chunk {{
    border-radius: 6px;
    background: {tokens['progress_chunk']};
}}
QLabel#Notice {{
    padding: 10px 14px;
    border-radius: 8px;
    background: {tokens['notice_bg']};
    color: {tokens['notice_text']};
    font-size: 13px;
    border: 1px solid {tokens['accent_tint_border']};
}}
QScrollArea {{
    border: 0;
    background: transparent;
}}
QScrollBar:vertical {{
    width: 8px;
    background: transparent;
    margin: 2px 0 2px 0;
}}
QScrollBar::handle:vertical {{
    background: {tokens['border_strong']};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {tokens['text_muted']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QToolTip {{
    background: {tokens['text_main']};
    color: {tokens['bg_surface']};
    padding: 6px 10px;
    border-radius: 6px;
    border: 0;
    font-size: 12px;
}}
QCheckBox {{
    spacing: 8px;
    color: {tokens['text_main']};
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid {tokens['border_strong']};
    background: {tokens['bg_surface']};
}}
QCheckBox::indicator:hover {{
    border-color: {tokens['accent']};
}}
QCheckBox::indicator:checked {{
    background: {tokens['accent']};
    border-color: {tokens['accent']};
}}
"""

STYLE = get_theme_stylesheet("light")
