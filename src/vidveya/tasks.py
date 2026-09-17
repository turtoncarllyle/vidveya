"""Main-thread download scheduler; each attempt owns one isolated worker process."""
from collections import deque
import json
import math
import os
from pathlib import Path
import time
import uuid

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from .engine import cleanup_staging, staging_dir
from .models import ACTIVE_STATES, RUNNING_STATES, WAITING_STATES, UserError
from .processes import WorkerThread
from .store import Store, timestamp
from .urls import normalize_url


def bounded_int(value, default, low, high):
    try:
        return max(low, min(high, int(value)))
    except (ValueError, TypeError, OverflowError):
        return default


class _Attempt(QObject):
    """QObject slots ensure worker signals reach SQLite only on the GUI thread."""

    def __init__(self, manager, job_id, number, worker):
        super().__init__(manager)
        self.manager, self.job_id, self.number, self.worker = manager, job_id, number, worker
        self.outcome = None
        worker.event_received.connect(self.progress)
        worker.result_received.connect(self.result)
        worker.failure_received.connect(self.failure)
        worker.cancelled_signal.connect(self.cancelled)
        worker.finished.connect(self.finished)

    @Slot(dict)
    def progress(self, event):
        self.manager._progress(self, event)

    @Slot(dict)
    def result(self, result):
        self.outcome = ("result", result)

    @Slot(dict)
    def failure(self, error):
        self.outcome = ("error", error)

    @Slot()
    def cancelled(self):
        self.outcome = ("cancelled", {})

    @Slot()
    def finished(self):
        self.manager._finished(self)


class DownloadManager(QObject):
    job_changed = Signal(str)
    job_removed = Signal(str)
    completed = Signal(str)
    summary_changed = Signal()
    drained = Signal()

    def __init__(self, store: Store, parent=None, *, worker_factory=WorkerThread, clock=time.time):
        super().__init__(parent)
        self.store, self.worker_factory, self.clock = store, worker_factory, clock
        self.jobs = {}
        self.progress = {}
        self.active = {}
        self.queue = deque()
        self._queue_counter = 0
        self.ready = False
        self.closing = False
        self._pumping = False
        self.max_parallel = bounded_int(store.get_setting("max_parallel_downloads", 3), 3, 1, 5)
        self._restore()
        self.paused = any(job["state"] in WAITING_STATES for job in self.jobs.values())
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def get(self, job_id):
        return self.jobs.get(job_id) or self.store.job(job_id)

    def _save(self, job):
        if job["state"] not in ACTIVE_STATES:
            job.setdefault("finished_at", self.clock())
        self.store.save_job(job)
        self.job_changed.emit(job["id"])
        self.summary_changed.emit()

    def _receipt_path(self, job):
        return staging_dir(Path(job["directory"]), job["id"]).parent / f"{job['id']}.completed.json"

    def _read_receipt(self, job):
        try:
            result = json.loads(self._receipt_path(job).read_text(encoding="utf-8"))
            final = Path(result["path"])
            check = result["verification"]
            if (final.is_file() and final.parent.resolve() == Path(job["directory"]).resolve()
                    and check.get("audio_channels", 0) > 0 and check.get("width", 0) > 0
                    and check.get("height", 0) > 0 and check.get("duration", 0) > 0):
                return result
        except (OSError, ValueError, KeyError, TypeError, UserError):
            pass
        return None

    def _cleanup(self, job, receipt=False):
        try:
            if receipt:
                self._receipt_path(job).unlink(missing_ok=True)
            cleanup_staging(Path(job["directory"]), job["id"])
        except (OSError, ValueError, KeyError, UserError):
            pass

    def _restore(self):
        pending = self.store.pending_jobs()
        for index, job in enumerate(pending, 1):
            job.setdefault("queue_order", index)
        self._queue_counter = max((job["queue_order"] for job in pending), default=0)
        for job in sorted(pending, key=lambda item: item["queue_order"]):
            job.setdefault("attempts", 0)
            job.setdefault("retry_limit", 3)
            job.setdefault("next_retry_at", None)
            result = self._read_receipt(job)
            if result:
                job.update(state="completed", result=result, error="", next_retry_at=None)
            elif job.get("cancel_requested") or job.get("delete_requested"):
                job.update(state="cancelled", next_retry_at=None)
            elif job["state"] in RUNNING_STATES:
                job.update(state="interrupted", error="上次程序退出，任务已中断。可以重新下载。")
            self.store.save_job(job)
            self._cleanup(job, receipt=bool(result) or bool(job.get("delete_requested")))
            if job.get("delete_requested"):
                self.store.delete_job(job["id"])
                continue
            self.jobs[job["id"]] = job
            if job["state"] == "queued":
                self.queue.append(job["id"])

    def enqueue(self, info, option, directory):
        if self.closing:
            raise UserError("应用正在退出，无法添加任务。")
        url = normalize_url(info["url"])
        directory = str(Path(directory).expanduser().resolve())
        for job in self.jobs.values():
            if (job["state"] in ACTIVE_STATES and not job.get("delete_requested")
                    and job["url"] == url and job["option"]["key"] == option["key"]
                    and os.path.normcase(job["directory"]) == os.path.normcase(directory)):
                return job, False
        limit = bounded_int(self.store.get_setting("auto_retry_count", 3), 3, 0, 10)
        job = {"id": str(uuid.uuid4()), "created": timestamp(), "url": url, "title": info["title"],
               "option": dict(option), "directory": directory, "state": "queued", "error": "",
               "attempts": 0, "retry_limit": limit, "next_retry_at": None,
               "delete_requested": False, "cancel_requested": False}
        self.jobs[job["id"]] = job
        self._queue_counter += 1
        job["queue_order"] = self._queue_counter
        self.queue.append(job["id"])
        self._save(job)
        self._pump()
        return job, True

    def retry(self, job_id):
        job = self.get(job_id)
        if not job or job["state"] in ACTIVE_STATES or job_id in self.active or self.closing:
            return None
        return self.enqueue(job, job["option"], job["directory"])

    def set_ready(self, ready):
        self.ready = ready
        self._pump()

    def set_max_parallel(self, value):
        self.max_parallel = bounded_int(value, 3, 1, 5)
        self.store.set_setting("max_parallel_downloads", self.max_parallel)
        self.summary_changed.emit()
        self._pump()

    def pause_queue(self):
        """Stop dispatching new attempts; running downloads still finish normally."""
        if self.closing:
            return
        self.paused = True
        self.summary_changed.emit()

    def resume_queue(self):
        if self.closing:
            return
        self.paused = False
        self.tick()
        self.summary_changed.emit()

    def tick(self):
        if self.closing:
            return
        for job in list(self.jobs.values()):
            if job["state"] != "retry_wait":
                continue
            if not self.paused and self.clock() >= (job.get("next_retry_at") or 0):
                job.update(state="queued", next_retry_at=None)
                self._queue_counter += 1
                job["queue_order"] = self._queue_counter
                self.queue.append(job["id"])
                self._save(job)
            else:
                self.job_changed.emit(job["id"])
        self._pump()

    def _pump(self):
        if self._pumping or self.closing or self.paused or not self.ready:
            return
        self._pumping = True
        try:
            while self.queue and len(self.active) < self.max_parallel:
                job = self.jobs.get(self.queue.popleft())
                if not job or job["state"] != "queued" or job.get("delete_requested"):
                    continue
                result = self._read_receipt(job)
                if result:
                    self._complete(job, result)
                    continue
                self._start(job)
        finally:
            self._pumping = False

    def _start(self, job):
        job.update(state="starting", attempts=job["attempts"] + 1, next_retry_at=None, cancel_requested=False)
        self.progress[job["id"]] = {"state": "starting", "percent": None}
        request = {"command": "download", "job_id": job["id"], "attempt": job["attempts"],
                   "url": job["url"], "option_key": job["option"]["key"], "directory": job["directory"],
                   "proxy": self.store.get_setting("proxy", ""),
                   "use_auth": self.store.get_setting("use_auth", False)}
        try:
            worker = self.worker_factory(request, self)
            attempt = _Attempt(self, job["id"], job["attempts"], worker)
            self.active[job["id"]] = attempt
            self._save(job)
            worker.start()
        except Exception as error:
            attempt = self.active.pop(job["id"], None)
            if attempt:
                attempt.worker.deleteLater()
                attempt.deleteLater()
            self._fail(job, {"message": f"无法启动下载组件：{error}", "code": "component", "retryable": False})

    def _current(self, attempt):
        return self.active.get(attempt.job_id) is attempt

    def _progress(self, attempt, event):
        if not self._current(attempt) or self.closing:
            return
        job = self.jobs[attempt.job_id]
        if job.get("cancel_requested") or job.get("delete_requested"):
            return
        state = event.get("state")
        if state not in RUNNING_STATES:
            return
        event = dict(event)
        if event.get("percent") is not None:
            event["percent"] = max(0, min(99, int(event["percent"])))
        self.progress[job["id"]] = event
        if state != job["state"]:
            job["state"] = state
            self._save(job)
        else:
            self.job_changed.emit(job["id"])
            self.summary_changed.emit()

    def _finished(self, attempt):
        if not self._current(attempt):
            return
        job = self.jobs[attempt.job_id]
        del self.active[attempt.job_id]
        kind, data = attempt.outcome or ("error", {"message": "后台组件意外退出。", "retryable": False})
        result = data if kind == "result" else self._read_receipt(job)
        if result:
            self._complete(job, result)
        elif job.get("delete_requested") or job.get("cancel_requested") or self.closing or kind == "cancelled":
            job.update(state="interrupted" if self.closing and not job.get("cancel_requested") else "cancelled",
                       error="应用退出，任务已中断。" if self.closing else "下载已取消。", next_retry_at=None)
            self._save(job)
            self._cleanup(job)
        else:
            self._fail(job, data)
        if job.get("delete_requested"):
            self._remove(job)
        attempt.worker.deleteLater()
        attempt.deleteLater()
        self.summary_changed.emit()
        self._pump()
        if self.closing and not self.active:
            self.drained.emit()

    def _complete(self, job, result):
        job.update(state="completed", result=result, error="", next_retry_at=None)
        self.progress[job["id"]] = {"state": "completed", "percent": 100}
        self._save(job)
        self._cleanup(job, receipt=True)
        if not self.closing and not job.get("delete_requested"):
            self.completed.emit(job["id"])

    def _fail(self, job, error):
        job["error"] = str(error.get("message") or "后台组件意外退出。")
        job["error_code"] = str(error.get("code", "unknown"))
        self.progress.pop(job["id"], None)
        if error.get("retryable") is True and job["attempts"] <= job["retry_limit"] and not self.closing:
            delay = (10, 30, 60)[min(max(job["attempts"] - 1, 0), 2)]
            if error.get("code") == "http_429":
                delay = max(60, delay)
            retry_after = error.get("retry_after_seconds")
            if isinstance(retry_after, (float, int)) and math.isfinite(retry_after):
                delay = max(delay, retry_after)
            job.update(state="retry_wait", next_retry_at=self.clock() + delay)
        else:
            job.update(state="failed", next_retry_at=None)
        self._save(job)
        self._cleanup(job)

    def cancel(self, job_id):
        job = self.jobs.get(job_id)
        if not job or job["state"] not in ACTIVE_STATES:
            return
        job.update(cancel_requested=True, next_retry_at=None)
        self.queue = deque(identity for identity in self.queue if identity != job_id)
        if job_id in self.active:
            self._save(job)
            self.active[job_id].worker.cancel()
        else:
            job.update(state="cancelled", error="下载已取消。")
            self._save(job)
            self._cleanup(job)
        self._pump()

    def delete(self, job_id):
        job = self.get(job_id)
        if not job or self.closing:
            return
        self.jobs[job_id] = job
        job.update(delete_requested=True, next_retry_at=None)
        self._save(job)
        self.cancel(job_id)
        if job_id not in self.active:
            self._remove(job)

    def _remove(self, job):
        if job["id"] in self.active:
            return
        self._cleanup(job, receipt=True)
        if self.store.delete_job(job["id"]):
            self.queue = deque(identity for identity in self.queue if identity != job["id"])
            self.jobs.pop(job["id"], None)
            self.progress.pop(job["id"], None)
            self.job_removed.emit(job["id"])
            self.summary_changed.emit()

    def forget_finished(self):
        for job_id, job in list(self.jobs.items()):
            if job["state"] not in ACTIVE_STATES and job_id not in self.active and self.store.job(job_id) is None:
                self.jobs.pop(job_id)
                self.progress.pop(job_id, None)
                self.job_removed.emit(job_id)
        self.summary_changed.emit()

    def summary(self):
        waiting = sum(job["state"] in WAITING_STATES for job in self.jobs.values())
        speed = sum((self.progress.get(job_id, {}).get("speed") or 0) for job_id in self.active
                    if self.jobs[job_id]["state"] == "downloading" and not self.jobs[job_id].get("cancel_requested"))
        return {"running": len(self.active), "waiting": waiting, "speed": speed}

    def shutdown(self):
        if self.closing:
            return
        self.closing = True
        self.ready = False
        self.timer.stop()
        for attempt in list(self.active.values()):
            attempt.worker.cancel()
        if not self.active:
            self.drained.emit()
