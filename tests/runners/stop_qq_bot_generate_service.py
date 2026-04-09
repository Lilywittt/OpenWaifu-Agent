from __future__ import annotations

"""优雅停止 QQ 私聊生成服务。"""

import sys
import time
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
    request_service_stop,
)


def main() -> int:
    configure_utf8_stdio()
    if cleanup_stale_service_lock(PROJECT_DIR):
        print("[qq-generate-stop] 发现并清理了残留锁，当前没有运行中的服务。", flush=True)
        return 0
    lock_payload = read_service_lock(PROJECT_DIR)
    status_payload = read_service_status(PROJECT_DIR)
    if not lock_payload or not is_service_running(PROJECT_DIR):
        print("[qq-generate-stop] 当前没有运行中的服务。", flush=True)
        return 0

    request_service_stop(PROJECT_DIR, reason="manual stop")
    pid = lock_payload.get("pid", "")
    print(f"[qq-generate-stop] 已发送停止请求，pid={pid}", flush=True)

    deadline = time.time() + 30.0
    while time.time() < deadline:
        lock_payload = read_service_lock(PROJECT_DIR)
        status_payload = read_service_status(PROJECT_DIR)
        if not lock_payload:
            print("[qq-generate-stop] 服务已停止。", flush=True)
            return 0
        if status_payload:
            print(
                f"[qq-generate-stop] 等待停止中，当前状态={status_payload.get('status', 'unknown')}，"
                f"阶段={status_payload.get('stage', '')}",
                flush=True,
            )
        time.sleep(1.0)

    print("[qq-generate-stop] 停止请求已发出，但服务仍未完全退出。", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
