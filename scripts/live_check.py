"""Exercise the real source or packaged worker and save a reviewable report."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def run(command, payload, environment):
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=environment, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
    process.stdin.close()
    last_state = None
    result = None
    for raw in process.stdout:
        event = json.loads(raw)
        if event.get("state") != last_state and event.get("state"):
            last_state = event["state"]
            print(last_state, flush=True)
        if event["event"] == "error":
            raise RuntimeError(event["message"])
        if event["event"] == "result":
            result = event["data"]
    if process.wait() != 0 or result is None:
        raise RuntimeError(process.stderr.read().decode("utf-8", "replace")[-1500:])
    return result


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://www.youtube.com/watch?v=YE7VzlLtp-4")
    parser.add_argument("--resolution", type=int, default=360)
    parser.add_argument("--container", default="mp4")
    parser.add_argument("--worker")
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()
    command = [args.worker] if args.worker else [sys.executable, str(ROOT / "worker_entry.py")]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PYTHONUTF8"] = "1"
    if args.worker:
        env.pop("PYTHONPATH", None)
        env.pop("VIRTUAL_ENV", None)
        env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    started = time.monotonic()
    info = run(command, {"command": "analyze", "url": args.url}, env)
    folder = ROOT / "artifacts" / "live"
    folder.mkdir(parents=True, exist_ok=True)
    options = [item for item in info["options"] if item["resolution"] == args.resolution and item["container"] == args.container]
    if not options:
        raise RuntimeError(f"Resolution unavailable; available: {[(x['resolution'], x['container']) for x in info['options']]}")
    result = None
    if not args.analyze_only:
        result = run(command, {"command": "download", "url": args.url, "job_id": str(uuid.uuid4()),
                               "option_key": options[0]["key"], "directory": str(folder / "下载视频")}, env)
    report = {"source": "packaged" if args.worker else "source", "elapsed_seconds": time.monotonic() - started,
              "video": info, "selected": options[0], "result": result}
    report_path = folder / f"{info['video_id']}-{args.resolution}-{args.container}-{'packaged' if args.worker else 'source'}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(report_path), "elapsed_seconds": round(report["elapsed_seconds"], 1), "result": result}, ensure_ascii=False))
