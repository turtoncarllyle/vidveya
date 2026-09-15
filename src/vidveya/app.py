import argparse
import json
import os
from pathlib import Path
import sys

from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from . import __version__
from .paths import data_dir, resource_root
from .store import Store
from .ui.style import STYLE
from .ui.window import MainWindow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshot", help="Capture the UI to a PNG, then exit (QA)")
    parser.add_argument("--fixture", help="Load a recorded public metadata fixture (QA)")
    args = parser.parse_args()
    application = QApplication(sys.argv[:1])
    application.setApplicationName("VidVeya")
    application.setApplicationVersion(__version__)
    application.setOrganizationName("VidVeya")
    application.setFont(QFont("Segoe UI", 10))
    application.setStyle("Fusion")
    application.setStyleSheet(STYLE)
    icon = resource_root() / "assets" / "vidveya.ico"
    if icon.exists():
        application.setWindowIcon(QIcon(str(icon)))
    root = data_dir()
    lock = QLockFile(str(root / "application.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, "VidVeya", "VidVeya 已在运行，请切换到已打开的窗口。")
        return 0
    store = Store(root / "vidveya.db")
    window = MainWindow(store)
    window.show()
    if args.fixture:
        fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        window.url_input.setText(fixture.get("video", fixture)["url"])
        window.show_video(fixture.get("video", fixture))
    if args.screenshot:
        def capture():
            destination = Path(args.screenshot).resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(destination))
            window.close()
        QTimer.singleShot(6000, capture)
    try:
        return application.exec()
    finally:
        store.close()
        lock.unlock()


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())
