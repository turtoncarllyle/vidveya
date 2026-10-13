import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import uuid

from PySide6.QtCore import QThread, Signal

from .paths import configure_component_environment, data_dir, executable_suffix, resource_root


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


def terminate_process_tree(process, *, force=False):
    """Terminate the worker and its media-tool children on Windows and macOS."""
    if process is None or process.poll() is not None:
        return
    if sys.platform == "win32":
        process.kill()
        return
    try:
        os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    if force and process.poll() is None:
        process.kill()


def worker_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).parent / f"VidVeya.Worker{executable_suffix()}")]
    return [sys.executable, str(resource_root() / "worker_entry.py")]


class WorkerThread(QThread):
    event_received = Signal(dict)
    result_received = Signal(dict)
    error_received = Signal(str)
    failure_received = Signal(dict)
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
                terminate_process_tree(self.process)

    def run(self):
        result = None
        error = None
        logs = data_dir() / "logs"
        logs.mkdir(exist_ok=True)
        environment = configure_component_environment()
        environment["PYTHONUTF8"] = "1"
        if not getattr(sys, "frozen", False):
            environment["PYTHONPATH"] = str(resource_root() / "src")
        try:
            log_name = (f"download-{uuid.UUID(self.request['job_id'])}-{int(self.request.get('attempt', 1))}.log"
                        if self.request.get("command") == "download" else "worker.log")
            with (logs / log_name).open("ab") as log:
                with self.lock:
                    if self.cancelled.is_set():
                        self.cancelled_signal.emit()
                        return
                    self.process = subprocess.Popen(
                        worker_command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        start_new_session=sys.platform != "win32", env=environment,
                    )
                    try:
                        self.guard = JobGuard(self.process)
                    except Exception:
                        terminate_process_tree(self.process, force=True)
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
                        error = message
                    else:
                        self.event_received.emit(message)
                returncode = self.process.wait()
                if self.cancelled.is_set():
                    self.cancelled_signal.emit()
                elif result is not None and returncode == 0:
                    self.result_received.emit(result)
                else:
                    self.emit_failure(error or {"message": "后台组件意外退出，请在设置中检查组件或重新安装。",
                                                "code": "component", "retryable": False})
        except Exception as exception:
            if self.cancelled.is_set():
                self.cancelled_signal.emit()
            else:
                self.emit_failure({"message": f"无法运行下载组件：{exception}",
                                   "code": "component", "retryable": False})
        finally:
            with self.lock:
                if self.guard:
                    self.guard.close()
                if self.process:
                    if self.process.poll() is None:
                        terminate_process_tree(self.process, force=True)
                    self.process.wait()
                    if self.process.stdout:
                        self.process.stdout.close()

    def emit_failure(self, error):
        self.failure_received.emit(error)
        self.error_received.emit(error["message"])
