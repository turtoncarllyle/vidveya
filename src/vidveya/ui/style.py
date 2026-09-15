# A quiet Windows workspace with one strong identifier: red resolution badges.
STYLE = """
QMainWindow, QWidget#Workspace { background: #F7F8FA; }
QWidget { font-family: 'Microsoft YaHei UI'; font-size: 14px; color: #20242C; }
QFrame#Sidebar { background: #FFFFFF; border-right: 1px solid #E5E7EC; }
QLabel#Brand { font-family: 'Bahnschrift', 'Segoe UI'; font-size: 27px; font-weight: 700; }
QLabel#Eyebrow { color: #69717E; font-size: 12px; }
QLabel#Heading { font-size: 25px; font-weight: 700; }
QLabel#Subheading { font-size: 16px; font-weight: 600; }
QLabel#Muted { color: #69717E; }
QLabel#Status { color: #69717E; font-size: 12px; }
QLabel#ProgressValue { color: #CE2E37; font-size: 16px; font-weight: 700; }
QFrame#Card { background: #FFFFFF; border: 1px solid #E5E7EC; border-radius: 12px; }
QFrame#Card QLabel, QFrame#Card QWidget { background: transparent; }
QPushButton { background: #FFFFFF; border: 1px solid #DCE0E7; border-radius: 7px; padding: 9px 16px; font-weight: 600; }
QPushButton:hover { background: #F4F5F7; border-color: #C4CAD3; }
QPushButton:pressed { background: #EAECEF; }
QPushButton:focus { border: 2px solid #E33D45; padding: 8px 15px; }
QPushButton:disabled { color: #9CA3AF; background: #F1F2F5; border-color: #E8EAF0; }
QPushButton#Primary { color: #FFFFFF; background: #E33D45; border-color: #E33D45; }
QPushButton#Primary:hover { background: #CE2E37; }
QPushButton#Primary:disabled { background: #EEADB1; border-color: #EEADB1; }
QPushButton#Navigation { text-align: left; border: 0; background: transparent; padding: 12px 16px; font-weight: 400; }
QPushButton#Navigation:checked { color: #CE2E37; background: #FFF0F1; font-weight: 700; }
QPushButton#Navigation:hover { background: #F7F8FA; }
QPushButton#Mode { padding: 8px 20px; }
QPushButton#Mode:checked { color: #CE2E37; background: #FFF0F1; border-color: #F1ADB2; }
QLineEdit { background: #FFFFFF; border: 1px solid #DCE0E7; border-radius: 7px; padding: 10px 12px; selection-background-color: #E33D45; }
QLineEdit:focus { border: 2px solid #E33D45; padding: 9px 11px; }
QComboBox { background: #FFFFFF; border: 1px solid #DCE0E7; border-radius: 7px; padding: 10px 12px; }
QComboBox:focus { border: 2px solid #E33D45; padding: 9px 11px; }
QTableWidget { background: #FFFFFF; border: 1px solid #E5E7EC; border-radius: 8px; gridline-color: #EEF0F3; selection-background-color: #FFF0F1; selection-color: #20242C; }
QTableWidget::item { padding: 8px; border: 0; }
QHeaderView::section { background: #F7F8FA; color: #69717E; padding: 10px 8px; border: 0; border-bottom: 1px solid #E5E7EC; font-weight: 400; }
QProgressBar { border: 0; border-radius: 6px; background: #ECEEF2; text-align: center; }
QProgressBar::chunk { border-radius: 6px; background: #E33D45; }
QLabel#Notice { padding: 10px 12px; border-radius: 6px; background: #FFF0F1; color: #AC2630; }
QScrollArea { border: 0; background: transparent; }
QScrollBar:vertical { width: 9px; background: transparent; }
QScrollBar::handle:vertical { background: #D1D6DF; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { background: #20242C; color: #FFFFFF; padding: 6px; border: 0; }
"""
