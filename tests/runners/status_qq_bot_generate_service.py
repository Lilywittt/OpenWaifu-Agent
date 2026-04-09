from __future__ import annotations

"""查看 QQ 私聊生成服务当前状态。"""

import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
TOOLS_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
for import_path in (TOOLS_DIR, SRC_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from common import configure_utf8_stdio

from publish.qq_bot_generate_service import (
    cleanup_stale_service_lock,
    is_service_running,
    read_service_lock,
    read_service_status,
)


def main() -> int:
    configure_utf8_stdio()
    stale_lock_cleaned = cleanup_stale_service_lock(PROJECT_DIR)
    log_dir = PROJECT_DIR / "runtime" / "service_logs" / "publish"
    payload = {
        "lock": read_service_lock(PROJECT_DIR),
        "status": read_service_status(PROJECT_DIR),
        "running": is_service_running(PROJECT_DIR),
        "staleLockCleaned": stale_lock_cleaned,
        "logs": {
            "stdout": str(log_dir / "qq_bot_generate_service.stdout.log"),
            "stderr": str(log_dir / "qq_bot_generate_service.stderr.log"),
            "events": str(
                PROJECT_DIR
                / "runtime"
                / "service_state"
                / "publish"
                / "qq_bot_generate_service"
                / "service_events.jsonl"
            ),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
