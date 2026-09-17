import json
from pathlib import Path
import sqlite3
from datetime import datetime, timezone

from .models import ACTIVE_STATES, RUNNING_STATES


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.connection.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, created TEXT NOT NULL, data TEXT NOT NULL)")
        self.connection.commit()

    def get_setting(self, key: str, default=None):
        row = self.connection.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_setting(self, key: str, value):
        self.connection.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, json.dumps(value, ensure_ascii=False)))
        self.connection.commit()

    def save_job(self, job: dict):
        self.connection.execute("INSERT OR REPLACE INTO jobs VALUES (?, ?, ?)",
                                (job["id"], job["created"], json.dumps(job, ensure_ascii=False)))
        self.connection.commit()

    def jobs(self, limit: int = 500) -> list[dict]:
        rows = self.connection.execute("SELECT data FROM jobs ORDER BY created DESC, rowid DESC LIMIT ?", (limit,))
        return [json.loads(row[0]) for row in rows]

    def job_count(self) -> int:
        return self.connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    def has_finished_jobs(self) -> bool:
        states = sorted(ACTIVE_STATES)
        placeholders = ",".join("?" for _ in states)
        return bool(self.connection.execute(
            f"SELECT EXISTS(SELECT 1 FROM jobs WHERE json_extract(data, '$.state') NOT IN ({placeholders}))",
            states,
        ).fetchone()[0])

    def job(self, job_id: str) -> dict | None:
        row = self.connection.execute("SELECT data FROM jobs WHERE id=?", (job_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def pending_jobs(self) -> list[dict]:
        states = sorted(ACTIVE_STATES)
        placeholders = ",".join("?" for _ in states)
        rows = self.connection.execute(
            f"SELECT data FROM jobs WHERE json_extract(data, '$.state') IN ({placeholders}) "
            "OR json_extract(data, '$.delete_requested') = 1 ORDER BY created, rowid", states,
        )
        return [json.loads(row[0]) for row in rows]

    def recover(self):
        # Only the single desktop instance may call recovery.
        rows = self.connection.execute("SELECT data FROM jobs").fetchall()
        for row in rows:
            job = json.loads(row[0])
            if job["state"] in RUNNING_STATES:
                job.update(state="interrupted", error="上次程序意外退出，任务已中断。可以重新下载。")
                self.save_job(job)

    def delete_job(self, job_id: str) -> bool:
        states = sorted(ACTIVE_STATES)
        placeholders = ",".join("?" for _ in states)
        with self.connection:
            cursor = self.connection.execute(
                f"DELETE FROM jobs WHERE id=? AND json_extract(data, '$.state') NOT IN ({placeholders})",
                (job_id, *states),
            )
        return cursor.rowcount > 0

    def clear_jobs(self) -> int:
        states = sorted(ACTIVE_STATES)
        placeholders = ",".join("?" for _ in states)
        with self.connection:
            cursor = self.connection.execute(
                f"DELETE FROM jobs WHERE json_extract(data, '$.state') NOT IN ({placeholders})", states,
            )
        return cursor.rowcount

    def close(self):
        self.connection.close()
