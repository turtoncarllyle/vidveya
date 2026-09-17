import json
import sys

from .engine import analyze, download, friendly_error
from .failures import failure_details
from .media import diagnostics


def emit(message):
    sys.stdout.write(json.dumps(message, ensure_ascii=False, allow_nan=False) + "\n")
    sys.stdout.flush()


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        line = sys.stdin.readline(65537)
        if len(line) > 65536:
            raise ValueError("任务消息过大")
        request = json.loads(line)
        command = request["command"]
        if command == "analyze":
            result = analyze(request["url"], request.get("proxy", ""), bool(request.get("use_auth"))).to_dict()
        elif command == "download":
            result = download(request, emit)
        elif command == "diagnostics":
            result = diagnostics()
        else:
            raise ValueError("不支持的操作")
        emit({"event": "result", "data": result})
        return 0
    except Exception as error:
        emit({"event": "error", **failure_details(error, friendly_error(error))})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
