from __future__ import annotations

"""后台启动 QQ 私聊生成服务。"""

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

from publish.qq_bot_generate_service import cleanup_stale_service_lock, is_service_running, read_service_lock, read_service_status


def _service_log_paths(project_dir: Path) -> tuple[Path, Path, Path]:
    log_dir = project_dir / "runtime" / "service_logs" / "publish"
    return (
        log_dir / "qq_bot_generate_service.stdout.log",
        log_dir / "qq_bot_generate_service.stderr.log",
        project_dir / "runtime" / "service_state" / "publish" / "qq_bot_generate_service" / "service_events.jsonl",
    )


def _print_start_guidance(
    *,
    pid: str,
    status: dict | None,
    stdout_path: Path | None = None,
    stderr_path: Path | None = None,
    events_path: Path | None = None,
) -> None:
    resolved_status = status or {}
    print(f"[qq-generate-start] 服务已就绪，pid={pid}", flush=True)
    print(
        f"[qq-generate-start] 当前状态={resolved_status.get('status', 'unknown')}，"
        f"阶段={resolved_status.get('stage', '')}",
        flush=True,
    )
    print("[qq-generate-start] 下一步：", flush=True)
    print("  1. 去 QQ 私聊机器人", flush=True)
    print("  2. 体验者模式直接发送：生成", flush=True)
    print("  3. 查看进度发送：状态", flush=True)
    print("  4. 查看说明发送：帮助", flush=True)
    print("  5. 开发者模式依次发送：开发者模式 -> 注入场景稿 -> JSON", flush=True)
    print("[qq-generate-start] 服务控制：", flush=True)
    print("  - 查看状态：python tests/runners/qq_bot_generate_service_ctl.py status", flush=True)
    print("  - 停止服务：python tests/runners/qq_bot_generate_service_ctl.py stop", flush=True)
    if stdout_path is not None:
        print(f"[qq-generate-start] stdout={stdout_path}", flush=True)
    if stderr_path is not None:
        print(f"[qq-generate-start] stderr={stderr_path}", flush=True)
    if events_path is not None:
        print(f"[qq-generate-start] events={events_path}", flush=True)


def main() -> int:
    configure_utf8_stdio()
    cleanup_stale_service_lock(PROJECT_DIR)
    lock_payload = read_service_lock(PROJECT_DIR)
    if lock_payload:
        pid = lock_payload.get("pid", "")
        status = read_service_status(PROJECT_DIR)
        print(f"[qq-generate-start] 服务已经在运行。", flush=True)
        _print_start_guidance(pid=str(pid), status=status)
        return 0

    stdout_path, stderr_path, events_path = _service_log_paths(PROJECT_DIR)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)

    import subprocess

    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    process = subprocess.Popen(
        [str(Path(sys.executable)), "tests/runners/qq_bot_generate_service.py"],
        cwd=str(PROJECT_DIR),
        stdout=stdout_path.open("wb"),
        stderr=stderr_path.open("wb"),
        creationflags=creationflags,
    )
    deadline = time.time() + 10.0
    lock_payload = None
    while time.time() < deadline:
        lock_payload = read_service_lock(PROJECT_DIR)
        if lock_payload and is_service_running(PROJECT_DIR):
            break
        time.sleep(0.5)
    if not lock_payload or not is_service_running(PROJECT_DIR):
        print("[qq-generate-start] 后台启动失败，请查看服务日志。", flush=True)
        return 1

    status = read_service_status(PROJECT_DIR)
    _print_start_guidance(
        pid=str(lock_payload.get("pid", process.pid)),
        status=status,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        events_path=events_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
