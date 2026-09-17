from unittest.mock import Mock

from PySide6.QtCore import QObject, Signal


class FakeWorker(QObject):
    event_received = Signal(dict)
    result_received = Signal(dict)
    failure_received = Signal(dict)
    cancelled_signal = Signal()
    finished = Signal()

    def __init__(self, request, parent=None):
        super().__init__(parent)
        self.request = request
        self.running = False
        self.cancel = Mock()
        self.wait = Mock(return_value=True)

    def start(self):
        self.running = True

    def isRunning(self):
        return self.running

    def finish(self):
        self.running = False
        self.finished.emit()

    def succeed(self, result):
        self.result_received.emit(result)
        self.finish()

    def fail(self, code="network", retryable=True, **extra):
        self.failure_received.emit({"message": "QA failure", "code": code, "retryable": retryable, **extra})
        self.finish()


class WorkerFactory:
    def __init__(self):
        self.workers = []

    def __call__(self, request, parent):
        worker = FakeWorker(request, parent)
        self.workers.append(worker)
        return worker
