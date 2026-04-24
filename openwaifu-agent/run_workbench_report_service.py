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
from reporting.service import DEFAULT_POLL_SECONDS, run_workbench_report_service
from reporting.state import (
    cleanup_stale_service_lock,
    is_service_running,
    read_service_lock,
    read_service_status,
    reporting_logs_root,
    request_service_stop,
    sent_reports_path,
    service_events_path,
    service_status_path,
)


def configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _service_log_paths(project_dir: Path) -> tuple[Path, Path]:
    log_dir = reporting_logs_root(project_dir)
    return (
        log_dir / "workbench_report_service.stdout.log",
        log_dir / "workbench_report_service.stderr.log",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run or control the workbench QQ report listener.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    for command in ("start", "restart", "foreground"):
        sub = subparsers.add_parser(command)
        sub.add_argument(
            "--config",
            default=str(PROJECT_DIR / "config" / "reporting" / "workbench_report_service.json"),
        )
        sub.add_argument("--poll-seconds", type=int, default=DEFAULT_POLL_SECONDS)

    subparsers.add_parser("status")
    subparsers.add_parser("stop")
    return parser


def _print_start_guidance(*, pid: str, status: dict | None, stdout_path: Path, stderr_path: Path) -> None:
    resolved_status = status or {}
    print(f"[workbench-report] 服务已就绪，pid={pid}", flush=True)
    print(
        f"[workbench-report] 当前状态={resolved_status.get('status', 'unknown')} "
        f"阶段={resolved_status.get('stage', '')}",
        flush=True,
    )
    print("[workbench-report] 控制命令：", flush=True)
    print("  python run_workbench_report_service.py status", flush=True)
    print("  python run_workbench_report_service.py stop", flush=True)
    print("  python run_workbench_report_service.py foreground", flush=True)
    print(f"[workbench-report] stdout={stdout_path}", flush=True)
    print(f"[workbench-report] stderr={stderr_path}", flush=True)


def _foreground_main(args: argparse.Namespace) -> int:
    print("[workbench-report] 监听服务启动中", flush=True)
    print(f"[workbench-report] config={Path(args.config).resolve()}", flush=True)
    print(f"[workbench-report] pollSeconds={args.poll_seconds}", flush=True)
    return run_workbench_report_service(
        PROJECT_DIR,
        config_path=Path(args.config).resolve(),
        poll_seconds=args.poll_seconds,
        log=lambda message: print(message, flush=True),
    )


def _start_background(args: argparse.Namespace) -> int:
    cleanup_stale_service_lock(PROJECT_DIR)
    lock_payload = read_service_lock(PROJECT_DIR)
    if lock_payload and is_service_running(PROJECT_DIR):
        _print_start_guidance(
            pid=str(lock_payload.get("pid", "")),
            status=read_service_status(PROJECT_DIR),
            stdout_path=_service_log_paths(PROJECT_DIR)[0],
            stderr_path=_service_log_paths(PROJECT_DIR)[1],
        )
        return 0

    stdout_path, stderr_path = _service_log_paths(PROJECT_DIR)
    child_argv = [
        str(Path(sys.executable).resolve()),
        str(PROJECT_DIR / "run_workbench_report_service.py"),
        "foreground",
        "--config",
        str(Path(args.config).resolve()),
        "--poll-seconds",
        str(args.poll_seconds),
    ]
    try:
        pid = spawn_background_process(
            child_argv,
            cwd=str(PROJECT_DIR),
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            detached_from_parent_job=True,
        )
    except RuntimeError as exc:
        print("[workbench-report] 后台启动失败，请查看日志。", flush=True)
        print(f"[workbench-report] error={exc}", flush=True)
        print(f"[workbench-report] stdout={stdout_path}", flush=True)
        print(f"[workbench-report] stderr={stderr_path}", flush=True)
        return 1

    deadline = time.time() + 10.0
    while time.time() < deadline:
        lock_payload = read_service_lock(PROJECT_DIR)
        if lock_payload and is_service_running(PROJECT_DIR):
            break
        time.sleep(0.5)

    lock_payload = read_service_lock(PROJECT_DIR)
    if not lock_payload or not is_service_running(PROJECT_DIR):
        print("[workbench-report] 后台启动失败，请查看日志。", flush=True)
        print(f"[workbench-report] stdout={stdout_path}", flush=True)
        print(f"[workbench-report] stderr={stderr_path}", flush=True)
        return 1

    _print_start_guidance(
        pid=str(lock_payload.get("pid", pid)),
        status=read_service_status(PROJECT_DIR),
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )
    return 0


def _show_status() -> int:
    cleanup_stale_service_lock(PROJECT_DIR)
    payload = {
        "lock": read_service_lock(PROJECT_DIR),
        "status": read_service_status(PROJECT_DIR),
        "running": is_service_running(PROJECT_DIR),
        "paths": {
            "status": str(service_status_path(PROJECT_DIR)),
            "events": str(service_events_path(PROJECT_DIR)),
            "sentReports": str(sent_reports_path(PROJECT_DIR)),
            "stdout": str(_service_log_paths(PROJECT_DIR)[0]),
            "stderr": str(_service_log_paths(PROJECT_DIR)[1]),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0


def _stop_service() -> int:
    if cleanup_stale_service_lock(PROJECT_DIR):
        print("[workbench-report] 已清理残留锁。", flush=True)
        return 0
    lock_payload = read_service_lock(PROJECT_DIR)
    if not lock_payload or not is_service_running(PROJECT_DIR):
        print("[workbench-report] 当前没有运行中的服务。", flush=True)
        return 0
    pid = int(lock_payload.get("pid", 0) or 0)
    request_service_stop(PROJECT_DIR)
    print(f"[workbench-report] 已发送停止请求，pid={pid}", flush=True)

    deadline = time.time() + 20.0
    while time.time() < deadline:
        if not is_service_running(PROJECT_DIR):
            print("[workbench-report] 服务已停止。", flush=True)
            return 0
        time.sleep(0.5)

    if terminate_process(pid):
        time.sleep(1.0)
        cleanup_stale_service_lock(PROJECT_DIR)
        if not is_service_running(PROJECT_DIR):
            print("[workbench-report] 服务已强制停止。", flush=True)
            return 0
    print("[workbench-report] 停止请求已发出，但服务仍未退出。", flush=True)
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
