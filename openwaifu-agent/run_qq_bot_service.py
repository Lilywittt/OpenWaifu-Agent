from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from process_utils import spawn_background_process, terminate_process
from publish.qq_bot_router import (
    DEFAULT_HELP_COMMAND,
    DEFAULT_STATUS_COMMAND,
    DEFAULT_TRIGGER_COMMAND,
)
from publish.qq_bot_runtime_store import (
    QQGenerateServiceAlreadyRunningError,
    cleanup_stale_service_lock,
    is_service_running,
    qq_bot_generate_service_state_root,
    read_service_lock,
    read_service_status,
    request_service_stop,
)
from publish.qq_bot_service import (
    DEFAULT_RECONNECT_DELAY_SECONDS,
    run_qq_bot_generate_service,
)


def configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


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
    print(f"[qq-generate] 服务已就绪，pid={pid}", flush=True)
    print(
        f"[qq-generate] 当前状态={resolved_status.get('status', 'unknown')} "
        f"阶段={resolved_status.get('stage', '')}",
        flush=True,
    )
    print("[qq-generate] 下一步：", flush=True)
    print("  1. 去 QQ 私聊机器人", flush=True)
    print("  2. 体验者模式直接发送：生成", flush=True)
    print("  3. 查看进度发送：状态", flush=True)
    print("  4. 查看说明发送：帮助", flush=True)
    print("  5. 开发者模式依次发送：开发者模式 -> 注入场景稿 -> 正文或 JSON", flush=True)
    print("[qq-generate] 服务控制：", flush=True)
    print("  - 查看状态：python run_qq_bot_service.py status", flush=True)
    print("  - 停止服务：python run_qq_bot_service.py stop", flush=True)
    print("  - 前台调试：python run_qq_bot_service.py foreground", flush=True)
    if stdout_path is not None:
        print(f"[qq-generate] stdout={stdout_path}", flush=True)
    if stderr_path is not None:
        print(f"[qq-generate] stderr={stderr_path}", flush=True)
    if events_path is not None:
        print(f"[qq-generate] events={events_path}", flush=True)


def _add_service_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default=str(PROJECT_DIR / "config" / "publish" / "qq_bot_message.json"))
    parser.add_argument("--trigger-command", default=DEFAULT_TRIGGER_COMMAND)
    parser.add_argument("--help-command", default=DEFAULT_HELP_COMMAND)
    parser.add_argument("--status-command", default=DEFAULT_STATUS_COMMAND)
    parser.add_argument("--wait-seconds", type=int, default=0)
    parser.add_argument("--ready-only", action="store_true")
    parser.add_argument("--reconnect-delay-seconds", type=float, default=DEFAULT_RECONNECT_DELAY_SECONDS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run or control the QQ private-chat generate service.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    start = subparsers.add_parser("start", help="Start the QQ private-chat generate service in the background.")
    _add_service_runtime_args(start)

    restart = subparsers.add_parser("restart", help="Restart the QQ private-chat generate service.")
    _add_service_runtime_args(restart)

    foreground = subparsers.add_parser("foreground", help="Run the QQ private-chat generate service in the foreground.")
    _add_service_runtime_args(foreground)

    subparsers.add_parser("status", help="Print the current service status and log paths.")
    subparsers.add_parser("stop", help="Request a graceful service shutdown.")
    return parser


def _foreground_main(args: argparse.Namespace) -> int:
    state_root = qq_bot_generate_service_state_root(PROJECT_DIR)
    print(f"[qq-generate] 服务状态目录: {state_root}", flush=True)
    print(f"[qq-generate] 触发口令: {args.trigger_command}", flush=True)
    print(f"[qq-generate] 状态口令: {args.status_command}", flush=True)
    if args.ready_only:
        print("[qq-generate] 当前为 ready-only 模式。", flush=True)
    else:
        print("[qq-generate] 现在去 QQ 私聊机器人发送触发口令。", flush=True)

    def log(message: str) -> None:
        print(message, flush=True)

    try:
        run_qq_bot_generate_service(
            PROJECT_DIR,
            config_path=Path(args.config).resolve(),
            wait_seconds=args.wait_seconds,
            ready_only=args.ready_only,
            trigger_command=args.trigger_command,
            help_command=args.help_command,
            status_command=args.status_command,
            reconnect_delay_seconds=args.reconnect_delay_seconds,
            log=log,
        )
        return 0
    except KeyboardInterrupt:
        print("[qq-generate] 已收到退出请求，正在关闭服务。", flush=True)
        return 0
    except QQGenerateServiceAlreadyRunningError as exc:
        print(f"[qq-generate] 后台服务已经在运行，pid={exc.pid}", flush=True)
        status = read_service_status(PROJECT_DIR)
        if status:
            print(f"[qq-generate] 当前状态: {status.get('status', 'unknown')}", flush=True)
            print(f"[qq-generate] 当前阶段: {status.get('stage', '')}", flush=True)
            run_id = str(status.get("runId", "")).strip()
            if run_id:
                print(f"[qq-generate] 当前 runId: {run_id}", flush=True)
        return 0


def _start_background(args: argparse.Namespace) -> int:
    cleanup_stale_service_lock(PROJECT_DIR)
    lock_payload = read_service_lock(PROJECT_DIR)
    if lock_payload:
        status = read_service_status(PROJECT_DIR)
        print("[qq-generate] 服务已经在运行。", flush=True)
        _print_start_guidance(pid=str(lock_payload.get("pid", "")), status=status)
        return 0

    stdout_path, stderr_path, events_path = _service_log_paths(PROJECT_DIR)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)

    child_argv = [
        str(Path(sys.executable).resolve()),
        str(PROJECT_DIR / "run_qq_bot_service.py"),
        "foreground",
        "--config",
        str(Path(args.config).resolve()),
        "--trigger-command",
        args.trigger_command,
        "--help-command",
        args.help_command,
        "--status-command",
        args.status_command,
        "--wait-seconds",
        str(args.wait_seconds),
        "--reconnect-delay-seconds",
        str(args.reconnect_delay_seconds),
    ]
    if args.ready_only:
        child_argv.append("--ready-only")

    try:
        process_pid = spawn_background_process(
            child_argv,
            cwd=str(PROJECT_DIR),
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            detached_from_parent_job=True,
        )
    except RuntimeError as exc:
        print("[qq-generate] 后台启动失败，请查看服务日志。", flush=True)
        print(f"[qq-generate] error={exc}", flush=True)
        print(f"[qq-generate] stdout={stdout_path}", flush=True)
        print(f"[qq-generate] stderr={stderr_path}", flush=True)
        return 1

    deadline = time.time() + 10.0
    lock_payload = None
    while time.time() < deadline:
        lock_payload = read_service_lock(PROJECT_DIR)
        if lock_payload and is_service_running(PROJECT_DIR):
            break
        time.sleep(0.5)

    if not lock_payload or not is_service_running(PROJECT_DIR):
        print("[qq-generate] 后台启动失败，请查看服务日志。", flush=True)
        print(f"[qq-generate] stdout={stdout_path}", flush=True)
        print(f"[qq-generate] stderr={stderr_path}", flush=True)
        return 1

    status = read_service_status(PROJECT_DIR)
    _print_start_guidance(
        pid=str(lock_payload.get("pid", process_pid)),
        status=status,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        events_path=events_path,
    )
    return 0


def _show_status() -> int:
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


def _stop_service() -> int:
    if cleanup_stale_service_lock(PROJECT_DIR):
        print("[qq-generate] 已清理残留锁，当前没有运行中的服务。", flush=True)
        return 0

    lock_payload = read_service_lock(PROJECT_DIR)
    if not lock_payload or not is_service_running(PROJECT_DIR):
        print("[qq-generate] 当前没有运行中的服务。", flush=True)
        return 0

    pid = int(lock_payload.get("pid", 0) or 0)
    request_service_stop(PROJECT_DIR, reason="manual stop")
    print(f"[qq-generate] 已发送停止请求，pid={pid}", flush=True)

    deadline = time.time() + 30.0
    while time.time() < deadline:
        lock_payload = read_service_lock(PROJECT_DIR)
        status_payload = read_service_status(PROJECT_DIR)
        if not lock_payload:
            print("[qq-generate] 服务已停止。", flush=True)
            return 0
        if status_payload:
            print(
                f"[qq-generate] 等待停止中，当前状态={status_payload.get('status', 'unknown')} "
                f"阶段={status_payload.get('stage', '')}",
                flush=True,
            )
        time.sleep(1.0)

    if terminate_process(pid):
        time.sleep(1.0)
        cleanup_stale_service_lock(PROJECT_DIR)
        if not read_service_lock(PROJECT_DIR):
            print("[qq-generate] 服务已强制停止。", flush=True)
            return 0

    print("[qq-generate] 停止请求已发出，但服务仍未完全退出。", flush=True)
    return 1


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    if args.action == "foreground":
        return _foreground_main(args)
    if args.action == "start":
        return _start_background(args)
    if args.action == "status":
        return _show_status()
    if args.action == "stop":
        return _stop_service()
    if args.action == "restart":
        stop_result = _stop_service()
        if stop_result != 0:
            return stop_result
        return _start_background(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
