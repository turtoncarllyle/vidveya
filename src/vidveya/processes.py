import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys
import threading

from PySide6.QtCore import QThread, Signal

from .paths import data_dir, resource_root


class JobGuard:
    """Kill the entire worker/FFmpeg/Deno process tree if the desktop exits."""
    def __init__(self, process):
        self.handle = None
        if sys.platform != "win32":
            return

        class Limits(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOperationCount", "WriteOperationCount",
                       "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Limits), ("IoInfo", IO),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.kernel.CreateJobObjectW(None, None)
        limits = Extended()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.handle or not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())
        if not self.kernel.AssignProcessToJobObject(self.handle, wintypes.HANDLE(int(process._handle))):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def worker_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).parent / "VidVeya.Worker.exe")]
    return [sys.executable, str(resource_root() / "worker_entry.py")]


class WorkerThread(QThread):
    event_received = Signal(dict)
    result_received = Signal(dict)
    error_received = Signal(str)
    cancelled_signal = Signal()

    def __init__(self, request: dict, parent=None):
        super().__init__(parent)
        self.request = request
        self.cancelled = threading.Event()
        self.lock = threading.Lock()
        self.process = None
        self.guard = None

    def cancel(self):
        self.cancelled.set()
        with self.lock:
            if self.guard:
                self.guard.close()
            if self.process and self.process.poll() is None:
                self.process.kill()

    def run(self):
        import os
        result = None
        error = None
        logs = data_dir() / "logs"
        logs.mkdir(exist_ok=True)
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "1"
        if not getattr(sys, "frozen", False):
            environment["PYTHONPATH"] = str(resource_root() / "src")
        try:
            with (logs / "worker.log").open("ab") as log:
                with self.lock:
                    if self.cancelled.is_set():
                        self.cancelled_signal.emit()
                        return
                    self.process = subprocess.Popen(worker_command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                                    stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                                    env=environment)
                    try:
                        self.guard = JobGuard(self.process)
                    except Exception:
                        self.process.kill()
                        self.process.wait()
                        raise
                    self.process.stdin.write((json.dumps(self.request, ensure_ascii=False) + "\n").encode("utf-8"))
                    self.process.stdin.close()
                while True:
                    line = self.process.stdout.readline(1024 * 1024 + 1)
                    if not line:
                        break
                    if len(line) > 1024 * 1024:
                        raise ValueError("后台响应过大")
                    message = json.loads(line.decode("utf-8"))
                    if message["event"] == "result":
                        result = message["data"]
                    elif message["event"] == "error":
                        error = message["message"]
                    else:
                        self.event_received.emit(message)
                returncode = self.process.wait()
                if self.cancelled.is_set():
                    self.cancelled_signal.emit()
                elif result is not None and returncode == 0:
                    self.result_received.emit(result)
                else:
                    self.error_received.emit(error or "后台组件意外退出，请在设置中检查组件或重新安装。")
        except Exception as exception:
            if self.cancelled.is_set():
                self.cancelled_signal.emit()
            else:
                self.error_received.emit(f"无法运行下载组件：{exception}")
        finally:
            with self.lock:
                if self.guard:
                    self.guard.close()
                if self.process:
                    if self.process.poll() is None:
                        self.process.kill()
                    self.process.wait()
                    if self.process.stdout:
                        self.process.stdout.close()
