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

from roleplay_agent.config import load_app_config
from roleplay_agent.image_bridge import OpenWaifuAgentBridge
from roleplay_agent.process_utils import spawn_background_process, terminate_process
from roleplay_agent.qq.service import run_qq_publish_outlet
from roleplay_agent.runtime_store import (
    RoleplayOutletAlreadyRunningError,
    cleanup_stale_service_lock,
    is_service_running,
    read_service_lock,
    read_service_status,
    request_service_stop,
    service_events_path,
    service_log_root,
)


def configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    app_config = load_app_config(PROJECT_DIR)
    qq_service_config = app_config.get("qqService", {}) if isinstance(app_config.get("qqService", {}), dict) else {}
    parser = argparse.ArgumentParser(description="Run or control the QQ roleplay outlet.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    def add_runtime_args(target: argparse.ArgumentParser) -> None:
        target.add_argument("--config", default=str(PROJECT_DIR / "config" / "qq_bot.json"))
        target.add_argument("--ready-only", action="store_true")
        target.add_argument("--wait-seconds", type=int, default=int(qq_service_config.get("readyTimeoutSeconds", 0)))
        target.add_argument(
            "--reconnect-delay-seconds",
            type=float,
            default=float(qq_service_config.get("reconnectDelaySeconds", 3.0)),
        )
        target.add_argument("--skip-legacy-service-check", action="store_true")
        target.add_argument("--stop-legacy-service", action="store_true")

    add_runtime_args(subparsers.add_parser("foreground", help="Run the QQ roleplay outlet in foreground."))
    add_runtime_args(subparsers.add_parser("start", help="Start the QQ roleplay outlet in background."))
    add_runtime_args(subparsers.add_parser("restart", help="Restart the QQ roleplay outlet."))
    subparsers.add_parser("status", help="Print service status.")
    subparsers.add_parser("stop", help="Request graceful stop.")
    subparsers.add_parser("preflight", help="Check runtime dependencies and service conflicts.")
    return parser


def _log_paths() -> tuple[Path, Path]:
    log_root = service_log_root(PROJECT_DIR)
    return log_root / "qq_publish_outlet.stdout.log", log_root / "qq_publish_outlet.stderr.log"


def _preflight_payload() -> dict:
    bridge = OpenWaifuAgentBridge(PROJECT_DIR)
    cleanup_stale_service_lock(PROJECT_DIR)
    return {
        "roleplayOutlet": {
            "running": is_service_running(PROJECT_DIR),
            "lock": read_service_lock(PROJECT_DIR),
        },
        "imageBridge": bridge.preflight(),
    }


def _preflight() -> int:
    payload = _preflight_payload()
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0 if payload["imageBridge"].get("ok") else 1


def _foreground(args: argparse.Namespace) -> int:
    def log(message: str) -> None:
        print(message, flush=True)

    try:
        if args.stop_legacy_service:
            bridge = OpenWaifuAgentBridge(PROJECT_DIR, log=log)
            stopped = bridge.stop_legacy_service()
            if not stopped:
                print("[roleplay-qq] 旧 QQ 生图服务未能停止，取消接管。", flush=True)
                return 1
        run_qq_publish_outlet(
            PROJECT_DIR,
            config_path=Path(args.config).resolve(),
            ready_only=bool(args.ready_only),
            wait_seconds=int(args.wait_seconds),
            reconnect_delay_seconds=float(args.reconnect_delay_seconds),
            skip_legacy_service_check=bool(args.skip_legacy_service_check),
            log=log,
        )
        return 0
    except KeyboardInterrupt:
        print("[roleplay-qq] 已收到退出请求。", flush=True)
        return 0
    except RoleplayOutletAlreadyRunningError as exc:
        print(f"[roleplay-qq] 服务已经在运行，pid={exc.pid}", flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[roleplay-qq] 启动失败：{exc}", flush=True)
        return 1


def _start_background(args: argparse.Namespace) -> int:
    cleanup_stale_service_lock(PROJECT_DIR)
    lock_payload = read_service_lock(PROJECT_DIR)
    if lock_payload and is_service_running(PROJECT_DIR):
        print(f"[roleplay-qq] 服务已经在运行，pid={lock_payload.get('pid')}", flush=True)
        return 0
    if not args.skip_legacy_service_check:
        if args.stop_legacy_service:
            bridge = OpenWaifuAgentBridge(PROJECT_DIR)
            stopped = bridge.stop_legacy_service()
            if not stopped:
                print("[roleplay-qq] 旧 QQ 生图服务未能停止，取消接管。", flush=True)
                return 1
        payload = _preflight_payload()
        if not payload["imageBridge"].get("ok"):
            print("[roleplay-qq] preflight 未通过。", flush=True)
            print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
            return 1

    stdout_path, stderr_path = _log_paths()
    child_argv = [
        str(Path(sys.executable).resolve()),
        str(PROJECT_DIR / "run_qq_publish_outlet.py"),
        "foreground",
        "--config",
        str(Path(args.config).resolve()),
        "--wait-seconds",
        str(int(args.wait_seconds)),
        "--reconnect-delay-seconds",
        str(float(args.reconnect_delay_seconds)),
    ]
    if args.ready_only:
        child_argv.append("--ready-only")
    if args.skip_legacy_service_check:
        child_argv.append("--skip-legacy-service-check")
    if args.stop_legacy_service:
        child_argv.append("--stop-legacy-service")

    pid = spawn_background_process(
        child_argv,
        cwd=PROJECT_DIR,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        detached_from_parent_job=True,
    )
    deadline = time.time() + 10.0
    while time.time() < deadline:
        if is_service_running(PROJECT_DIR):
            status = read_service_status(PROJECT_DIR) or {}
            print(f"[roleplay-qq] 服务已启动，pid={pid}", flush=True)
            print(f"[roleplay-qq] 当前状态={status.get('status', 'unknown')} 阶段={status.get('stage', '')}", flush=True)
            print(f"[roleplay-qq] stdout={stdout_path}", flush=True)
            print(f"[roleplay-qq] stderr={stderr_path}", flush=True)
            return 0
        time.sleep(0.5)
    print("[roleplay-qq] 后台启动失败，请查看日志。", flush=True)
    print(f"[roleplay-qq] stdout={stdout_path}", flush=True)
    print(f"[roleplay-qq] stderr={stderr_path}", flush=True)
    return 1


def _stop() -> int:
    cleanup_stale_service_lock(PROJECT_DIR)
    lock_payload = read_service_lock(PROJECT_DIR)
    if not lock_payload or not is_service_running(PROJECT_DIR):
        print("[roleplay-qq] 当前没有运行中的服务。", flush=True)
        return 0
    pid = int(lock_payload.get("pid", 0) or 0)
    request_service_stop(PROJECT_DIR, reason="manual stop")
    print(f"[roleplay-qq] 已发送停止请求，pid={pid}", flush=True)
    deadline = time.time() + 20.0
    while time.time() < deadline:
        if not is_service_running(PROJECT_DIR):
            cleanup_stale_service_lock(PROJECT_DIR)
            print("[roleplay-qq] 服务已停止。", flush=True)
            return 0
        time.sleep(1.0)
    if terminate_process(pid):
        cleanup_stale_service_lock(PROJECT_DIR)
        print("[roleplay-qq] 服务已强制停止。", flush=True)
        return 0
    print("[roleplay-qq] 停止请求已发出，但服务仍未退出。", flush=True)
    return 1


def _status() -> int:
    cleanup_stale_service_lock(PROJECT_DIR)
    stdout_path, stderr_path = _log_paths()
    payload = {
        "running": is_service_running(PROJECT_DIR),
        "lock": read_service_lock(PROJECT_DIR),
        "status": read_service_status(PROJECT_DIR),
        "preflight": _preflight_payload(),
        "logs": {
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "events": str(service_events_path(PROJECT_DIR)),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    if args.action == "foreground":
        return _foreground(args)
    if args.action == "start":
        return _start_background(args)
    if args.action == "restart":
        stop_result = _stop()
        if stop_result != 0:
            return stop_result
        return _start_background(args)
    if args.action == "stop":
        return _stop()
    if args.action == "status":
        return _status()
    if args.action == "preflight":
        return _preflight()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
