import json
from pathlib import Path
import uuid

import pytest

from fakes import WorkerFactory
from vidveya.models import ACTIVE_STATES
from vidveya.store import Store
from vidveya.tasks import DownloadManager


@pytest.fixture
def scheduler(qapp, tmp_path):
    store = Store(tmp_path / "tasks.db")
    factory = WorkerFactory()
    now = [1000.0]
    manager = DownloadManager(store, worker_factory=factory, clock=lambda: now[0])
    manager.set_ready(True)
    yield manager, factory, now
    manager.shutdown()
    for attempt in list(manager.active.values()):
        attempt.worker.finish()
    manager.deleteLater()
    store.close()


def add(manager, tmp_path, number=0):
    return manager.enqueue({"title": f"视频 {number}", "url": f"https://youtu.be/YE7VzlLtp-{number}"},
                           {"key": "1920x1080:30:mp4", "resolution": 1080, "container": "mp4"},
                           str(tmp_path))[0]


def result_for(tmp_path, name="有声视频.mp4"):
    path = tmp_path / name
    path.write_bytes(b"video-audio-verified-fixture")
    return {"path": str(path), "verification": {"bytes": path.stat().st_size, "audio_channels": 2,
                                               "width": 1920, "height": 1080, "duration": 60}}


def test_three_parallel_two_queued_and_slot_lasts_until_finished(scheduler, tmp_path):
    manager, factory, _ = scheduler
    jobs = [add(manager, tmp_path, i) for i in range(5)]
    assert len(manager.active) == len(factory.workers) == 3
    assert [job["state"] for job in jobs] == ["starting"] * 3 + ["queued"] * 2
    worker = factory.workers[1]
    worker.result_received.emit(result_for(tmp_path))
    assert len(factory.workers) == 3
    worker.finish()
    assert len(factory.workers) == 4 and jobs[1]["state"] == "completed"
    assert jobs[3]["state"] == "starting" and jobs[4]["state"] == "queued"


def test_out_of_order_callbacks_cancel_and_progress_are_isolated(scheduler, tmp_path):
    manager, factory, _ = scheduler
    jobs = [add(manager, tmp_path, i) for i in range(3)]
    factory.workers[0].event_received.emit({"state": "downloading", "percent": 100, "speed": 100})
    factory.workers[2].event_received.emit({"state": "merging", "percent": None})
    assert manager.progress[jobs[0]["id"]]["percent"] == 99
    manager.cancel(jobs[1]["id"])
    factory.workers[1].cancel.assert_called_once()
    factory.workers[0].cancel.assert_not_called()
    factory.workers[1].finish()
    factory.workers[2].succeed(result_for(tmp_path))
    assert [job["state"] for job in jobs] == ["downloading", "cancelled", "completed"]


def test_limit_change_increases_capacity_without_cancelling_active(scheduler, tmp_path):
    manager, factory, _ = scheduler
    jobs = [add(manager, tmp_path, i) for i in range(6)]
    manager.set_max_parallel(5)
    assert len(factory.workers) == 5
    manager.set_max_parallel(1)
    for worker in factory.workers:
        worker.cancel.assert_not_called()
    for worker in factory.workers[:4]:
        worker.succeed(result_for(tmp_path))
    assert len(factory.workers) == 5 and jobs[5]["state"] == "queued"
    factory.workers[4].succeed(result_for(tmp_path))
    assert len(factory.workers) == 6


def test_default_three_retries_are_four_attempts_with_backoff(scheduler, tmp_path):
    manager, factory, now = scheduler
    job = add(manager, tmp_path)
    for index, delay in enumerate([10, 30, 60]):
        factory.workers[-1].fail()
        assert not manager.active and job["state"] == "retry_wait"
        assert job["next_retry_at"] == now[0] + delay
        now[0] += delay - 1
        manager.tick()
        assert len(factory.workers) == index + 1
        now[0] += 1
        manager.tick()
        assert len(factory.workers) == index + 2
    factory.workers[-1].fail()
    assert job["state"] == "failed" and job["attempts"] == 4
    now[0] += 999
    manager.tick()
    assert len(factory.workers) == 4


@pytest.mark.parametrize("retryable,limit", [(False, 3), (True, 0)])
def test_permanent_error_or_zero_limit_does_not_retry(scheduler, tmp_path, retryable, limit):
    manager, factory, now = scheduler
    manager.store.set_setting("auto_retry_count", limit)
    job = add(manager, tmp_path)
    factory.workers[0].fail(retryable=retryable)
    now[0] += 10000
    manager.tick()
    assert job["state"] == "failed" and len(factory.workers) == 1


def test_retries_yield_to_queue_and_ignore_old_attempt_callbacks(scheduler, tmp_path):
    manager, factory, now = scheduler
    manager.set_max_parallel(1)
    first, second = add(manager, tmp_path), add(manager, tmp_path, 1)
    old_attempt = manager.active[first["id"]]
    factory.workers[0].fail()
    assert second["state"] == "starting"
    now[0] += 10
    manager.tick()
    assert first["state"] == "queued"
    factory.workers[1].succeed(result_for(tmp_path))
    manager._progress(old_attempt, {"state": "merging", "percent": None})
    manager._finished(old_attempt)
    assert first["state"] == "starting" and first["attempts"] == 2
    factory.workers[2].succeed(result_for(tmp_path, "second.mp4"))
    assert first["state"] == "completed"


def test_rate_limit_respects_retry_after_and_new_setting_only_affects_new_jobs(scheduler, tmp_path):
    manager, factory, now = scheduler
    job = add(manager, tmp_path)
    manager.store.set_setting("auto_retry_count", 0)
    factory.workers[0].fail(code="http_429", retry_after_seconds=180)
    assert job["next_retry_at"] == now[0] + 180 and job["retry_limit"] == 3
    second = add(manager, tmp_path, 1)
    assert second["retry_limit"] == 0


def test_cancel_delete_retry_wait_and_queue_never_restart(scheduler, tmp_path):
    manager, factory, now = scheduler
    manager.set_max_parallel(1)
    first, second = add(manager, tmp_path), add(manager, tmp_path, 1)
    factory.workers[0].fail()
    manager.delete(first["id"])
    manager.cancel(second["id"])
    factory.workers[1].finish()
    now[0] += 999
    manager.tick()
    assert manager.store.job(first["id"]) is None
    assert second["state"] == "cancelled" and len(factory.workers) == 2


def test_delete_running_waits_for_exit_and_preserves_published_file(scheduler, tmp_path):
    manager, factory, _ = scheduler
    job = add(manager, tmp_path)
    result = result_for(tmp_path)
    manager.delete(job["id"])
    assert manager.store.job(job["id"])["delete_requested"]
    assert job["id"] in manager.active
    factory.workers[0].succeed(result)
    assert manager.store.job(job["id"]) is None and job["id"] not in manager.jobs
    assert Path(result["path"]).is_file()


def test_receipt_prevents_retry_even_if_worker_reports_cancel(scheduler, tmp_path):
    manager, factory, _ = scheduler
    job = add(manager, tmp_path)
    result = result_for(tmp_path)
    receipt = manager._receipt_path(job)
    receipt.parent.mkdir(exist_ok=True)
    receipt.write_text(json.dumps(result), encoding="utf-8")
    manager.cancel(job["id"])
    factory.workers[0].finish()
    assert job["state"] == "completed" and not receipt.exists()
    assert len(factory.workers) == 1


def test_duplicate_keys_and_manual_retry_have_new_identity_and_budget(scheduler, tmp_path):
    manager, factory, _ = scheduler
    job = add(manager, tmp_path)
    assert add(manager, tmp_path)["id"] == job["id"] and len(factory.workers) == 1
    factory.workers[0].fail(retryable=False)
    manager.store.set_setting("auto_retry_count", 2)
    repeated, created = manager.retry(job["id"])
    assert created and repeated["id"] != job["id"] and repeated["retry_limit"] == 2
    assert job["state"] == "failed"


def test_shutdown_cancels_all_workers_but_keeps_waiting_jobs(scheduler, tmp_path):
    manager, factory, now = scheduler
    jobs = [add(manager, tmp_path, i) for i in range(5)]
    manager.shutdown()
    for worker in list(factory.workers):
        worker.cancel.assert_called_once()
        worker.finish()
    assert [job["state"] for job in jobs] == ["interrupted"] * 3 + ["queued"] * 2
    now[0] += 999
    manager.tick()
    assert len(factory.workers) == 3 and not manager.active


def test_restore_includes_old_pending_records_and_requires_manual_resume(qapp, tmp_path):
    store = Store(tmp_path / "restart.db")
    base = {"title": "旧任务", "url": "https://youtu.be/YE7VzlLtp-4", "option": {"key": "1080"},
            "directory": str(tmp_path), "created": "2020-01-01", "attempts": 1, "retry_limit": 3}
    queue_id, retry_id, running_id, delete_id = [str(uuid.uuid4()) for _ in range(4)]
    for identity, state in [(queue_id, "queued"), (retry_id, "retry_wait"), (running_id, "downloading")]:
        store.save_job(base | {"id": identity, "state": state, "next_retry_at": 0})
    store.save_job(base | {"id": delete_id, "state": "starting", "delete_requested": True})
    with store.connection:
        store.connection.executemany("INSERT INTO jobs VALUES (?, ?, ?)",
                                    [(str(i), "2026", json.dumps({"id": str(i), "created": "2026", "state": "completed"}))
                                     for i in range(501)])
    factory = WorkerFactory()
    manager = DownloadManager(store, worker_factory=factory)
    manager.set_ready(True)
    assert manager.paused and not factory.workers
    assert store.job(running_id)["state"] == "interrupted" and store.job(delete_id) is None
    assert store.job(retry_id)["attempts"] == 1
    manager.resume_queue()
    assert len(factory.workers) == 2
    assert store.job(retry_id)["attempts"] == 2
    manager.shutdown()
    for worker in factory.workers:
        worker.finish()
    manager.deleteLater()
    store.close()


def test_clear_history_keeps_all_waiting_and_running_states(scheduler, tmp_path):
    manager, factory, _ = scheduler
    jobs = [add(manager, tmp_path, i) for i in range(5)]
    factory.workers[0].fail()
    manager.store.clear_jobs()
    assert len(manager.store.pending_jobs()) == 5
    assert all(job["state"] in ACTIVE_STATES for job in jobs)


def test_cancel_queued_job_renumbers_remaining_queue(scheduler, tmp_path):
    manager, factory, _ = scheduler
    manager.set_max_parallel(1)
    jobs = [add(manager, tmp_path, i) for i in range(4)]
    manager.cancel(jobs[1]["id"])
    manager.delete(jobs[2]["id"])
    assert list(manager.queue) == [jobs[3]["id"]]
    factory.workers[0].finish()
    assert factory.workers[-1].request["job_id"] == jobs[3]["id"]


def test_restart_preserves_requeued_order_and_receipts(qapp, tmp_path):
    store = Store(tmp_path / "restart.db")
    base = {"title": "恢复", "url": "https://youtu.be/YE7VzlLtp-4", "option": {"key": "1080"},
            "directory": str(tmp_path), "created": "2026-01-01", "attempts": 1, "retry_limit": 3}
    old, new, saved, deleted = [str(uuid.uuid4()) for _ in range(4)]
    for identity, order in [(old, 9), (new, 4), (saved, 5), (deleted, 6)]:
        store.save_job(base | {"id": identity, "state": "queued", "queue_order": order,
                              "delete_requested": identity == deleted})
    result = result_for(tmp_path)
    receipts = tmp_path / ".vidveya-tmp"
    receipts.mkdir()
    for identity in (saved, deleted):
        (receipts / f"{identity}.completed.json").write_text(json.dumps(result), encoding="utf-8")
    factory = WorkerFactory()
    manager = DownloadManager(store, worker_factory=factory)
    manager.set_max_parallel(1)
    manager.set_ready(True)
    assert not factory.workers and list(manager.queue) == [new, old]
    assert store.job(saved)["state"] == "completed" and store.job(deleted) is None
    assert Path(result["path"]).exists()
    manager.resume_queue()
    assert factory.workers[0].request["job_id"] == new
    manager.shutdown()
    factory.workers[0].finish()
    manager.deleteLater()
    store.close()


def test_shutdown_during_retry_wait_does_not_start_attempt(scheduler, tmp_path):
    manager, factory, now = scheduler
    job = add(manager, tmp_path)
    factory.workers[0].fail()
    manager.shutdown()
    now[0] += 999
    manager.tick()
    assert job["state"] == "retry_wait" and len(factory.workers) == 1
