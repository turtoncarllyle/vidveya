import json
from pathlib import Path
import sqlite3
from datetime import datetime, timezone

from .models import ACTIVE_STATES


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

    def recover(self):
        # Only the single desktop instance may call recovery.
        rows = self.connection.execute("SELECT data FROM jobs").fetchall()
        for row in rows:
            job = json.loads(row[0])
            if job["state"] in ACTIVE_STATES:
                job.update(state="interrupted", error="上次程序意外退出，任务已中断。可以重新下载。")
                self.save_job(job)

    def close(self):
        self.connection.close()
