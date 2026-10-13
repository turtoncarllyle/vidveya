from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_all, copy_metadata
from PyInstaller.building.osx import BUNDLE

root = Path(SPECPATH).parent
common_data = []
common_binaries = []
hidden = []
for package in ('yt_dlp', 'yt_dlp_ejs'):
    data, binaries, imports = collect_all(package)
    common_data += data
    common_binaries += binaries
    hidden += imports
for package in ('yt-dlp', 'yt-dlp-ejs', 'certifi', 'requests', 'urllib3', 'websockets', 'mutagen', 'pycryptodomex', 'brotli'):
    common_data += copy_metadata(package)
common_data += [
    (str(root / '.tooling' / 'runtime'), 'components'),
    (str(root / '.build' / 'licenses'), 'licenses'),
    (str(root / 'assets'), 'assets'),
]

# PyInstaller can discover ICU DLLs from the build machine's Poppler runtime.
# PySide6's Windows Qt build expects the Windows ICU ABI; bundling Poppler's
# ICU 78 files beside Qt6Core causes QtCore.pyd to fail with WinError 127 on
# machines whose system ICU is selected first. Keep those unrelated DLLs out
# of both GUI and worker collections.
def without_conflicting_icu(entries):
    blocked = {'icuuc.dll', 'icudt78.dll', 'icuin.dll'}
    return [entry for entry in entries if Path(str(entry[0])).name.lower() not in blocked]

common_binaries = without_conflicting_icu(common_binaries)

gui = Analysis([str(root / 'launcher.py')], pathex=[str(root / 'src')],
               binaries=common_binaries, datas=common_data, hiddenimports=hidden,
               excludes=['tkinter', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtTest'], noarchive=False)
worker = Analysis([str(root / 'worker_entry.py')], pathex=[str(root / 'src')],
                  binaries=common_binaries, datas=common_data, hiddenimports=hidden,
                  excludes=['PySide6', 'tkinter'], noarchive=False)
gui.binaries = without_conflicting_icu(gui.binaries)
worker.binaries = without_conflicting_icu(worker.binaries)
if sys.platform == 'win32':
    gui_exe = EXE(PYZ(gui.pure), gui.scripts, [], exclude_binaries=True, name='VidVeya',
                  console=False, icon=str(root / 'assets' / 'vidveya.ico'),
                  version=str(root / 'packaging' / 'version_info.txt'), upx=False)
    worker_exe = EXE(PYZ(worker.pure), worker.scripts, [], exclude_binaries=True, name='VidVeya.Worker',
                     console=True, icon=str(root / 'assets' / 'vidveya.ico'),
                     version=str(root / 'packaging' / 'version_info.txt'), upx=False)
else:
    gui_exe = EXE(PYZ(gui.pure), gui.scripts, [], exclude_binaries=True, name='VidVeya',
                  console=False, upx=False)
    worker_exe = EXE(PYZ(worker.pure), worker.scripts, [], exclude_binaries=True, name='VidVeya.Worker',
                     console=True, upx=False)
collection = COLLECT(gui_exe, worker_exe, gui.binaries, gui.datas, worker.binaries, worker.datas,
                     strip=False, upx=False, name='VidVeya')

# Let PyInstaller construct the macOS bundle itself.  The macOS bootloader
# expects the Python framework and native libraries under Contents/Frameworks;
# manually moving a normal onedir output into Contents/MacOS breaks that
# contract and produces "Failed to load Python shared library" at startup.
if sys.platform == 'darwin':
    app = BUNDLE(
        collection,
        name='VidVeya.app',
        version='0.2.0',
        bundle_identifier='com.vidveya.app',
        info_plist={
            'CFBundleVersion': '0.2.0',
            'LSMinimumSystemVersion': '12.0',
            'NSHighResolutionCapable': True,
        },
    )
