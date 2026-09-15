from pathlib import Path
from PyInstaller.utils.hooks import collect_all, copy_metadata

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

gui = Analysis([str(root / 'launcher.py')], pathex=[str(root / 'src')],
               binaries=common_binaries, datas=common_data, hiddenimports=hidden,
               excludes=['tkinter', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtTest'], noarchive=False)
worker = Analysis([str(root / 'worker_entry.py')], pathex=[str(root / 'src')],
                  binaries=common_binaries, datas=common_data, hiddenimports=hidden,
                  excludes=['PySide6', 'tkinter'], noarchive=False)
gui_exe = EXE(PYZ(gui.pure), gui.scripts, [], exclude_binaries=True, name='VidVeya',
              console=False, icon=str(root / 'assets' / 'vidveya.ico'),
              version=str(root / 'packaging' / 'version_info.txt'), upx=False)
worker_exe = EXE(PYZ(worker.pure), worker.scripts, [], exclude_binaries=True, name='VidVeya.Worker',
                 console=True, icon=str(root / 'assets' / 'vidveya.ico'),
                 version=str(root / 'packaging' / 'version_info.txt'), upx=False)
collection = COLLECT(gui_exe, worker_exe, gui.binaries, gui.datas, worker.binaries, worker.datas,
                     strip=False, upx=False, name='VidVeya')
