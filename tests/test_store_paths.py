import ctypes
from ctypes import wintypes
import sys
import uuid

import pytest

from vidveya.engine import cleanup_staging, staging_dir
from vidveya.paths import publish_file, safe_name
from vidveya.store import Store, timestamp


def test_persistence_and_recovery(tmp_path):
    db = tmp_path / "state.db"
    store = Store(db)
    store.set_setting("directory", "E:\\我的视频")
    for state in ("downloading", "converting", "completed"):
        store.save_job({"id": state, "state": state, "created": timestamp()})
    store.close()
    store = Store(db)
    store.recover()
    assert store.get_setting("directory") == "E:\\我的视频"
    jobs = {job["id"]: job for job in store.jobs()}
    assert jobs["downloading"]["state"] == "interrupted"
    assert jobs["converting"]["state"] == "interrupted"
    assert jobs["completed"]["state"] == "completed"
    store.close()


def test_unicode_and_reserved_filename():
    assert "中文" in safe_name('中文:标题*?', "YE7VzlLtp-4", 1080, "mp4")
    assert safe_name("CON", "YE7VzlLtp-4", 720, "mp4").startswith("_CON")


def test_atomic_publish_preserves_existing_file(tmp_path):
    existing = tmp_path / "片段.mp4"
    existing.write_bytes(b"original")
    source = tmp_path / "temp.mp4"
    source.write_bytes(b"new")
    result = publish_file(source, tmp_path, "片段.mp4")
    assert existing.read_bytes() == b"original"
    assert result.name == "片段 (1).mp4"


def test_cleanup_is_confined_to_job(tmp_path):
    job_id = str(uuid.uuid4())
    target = staging_dir(tmp_path, job_id)
    target.mkdir(parents=True)
    (target / "partial.mp4").write_bytes(b"data")
    keep = tmp_path / "my-file.mp4"
    keep.write_bytes(b"keep")
    cleanup_staging(tmp_path, job_id)
    assert keep.read_bytes() == b"keep"
    assert not target.exists()
    with pytest.raises(ValueError):
        staging_dir(tmp_path, "..\\..\\outside")


def test_more_than_four_gigabytes_uses_64_bit_file_sizes(tmp_path):
    source = tmp_path / "large.part"
    with source.open("wb") as output:
        if sys.platform == "win32":
            import msvcrt
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                               ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
            returned = wintypes.DWORD()
            kernel.DeviceIoControl(msvcrt.get_osfhandle(output.fileno()), 0x900C4, None, 0, None, 0, ctypes.byref(returned), None)
        output.truncate(4 * 1024**3 + 7)
    result = publish_file(source, tmp_path, "large.bin")
    assert result.stat().st_size == 4 * 1024**3 + 7
    result.unlink()
