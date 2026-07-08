from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .io_utils import ensure_dir, write_json
from .process_utils import is_process_alive


class RoleplayOutletAlreadyRunningError(RuntimeError):
    def __init__(self, pid: int):
        super().__init__(f"roleplay QQ publish outlet is already running with pid {pid}.")
        self.pid = int(pid)


class ServiceShutdownRequested(RuntimeError):
    pass


def service_state_root(project_dir: Path) -> Path:
    return ensure_dir(project_dir / "runtime" / "service_state" / "qq_publish_outlet")


def service_log_root(project_dir: Path) -> Path:
    return ensure_dir(project_dir / "runtime" / "service_logs")


def service_lock_path(project_dir: Path) -> Path:
    return service_state_root(project_dir) / "service.lock.json"


def service_stop_request_path(project_dir: Path) -> Path:
    return service_state_root(project_dir) / "stop.request.json"


def service_status_path(project_dir: Path) -> Path:
    return service_state_root(project_dir) / "latest_status.json"


def service_events_path(project_dir: Path) -> Path:
    return service_state_root(project_dir) / "service_events.jsonl"


def read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def read_service_lock(project_dir: Path) -> dict[str, Any] | None:
    return read_json_file(service_lock_path(project_dir))


def read_service_pid(project_dir: Path) -> int:
    payload = read_service_lock(project_dir) or {}
    try:
        return int(payload.get("pid", 0) or 0)
    except Exception:
        return 0


def is_service_running(project_dir: Path) -> bool:
    pid = read_service_pid(project_dir)
    return bool(pid and is_process_alive(pid))


def cleanup_stale_service_lock(project_dir: Path) -> bool:
    lock_path = service_lock_path(project_dir)
    if not lock_path.exists():
        return False
    pid = read_service_pid(project_dir)
    if pid and is_process_alive(pid):
        return False
    try:
        lock_path.unlink()
    except OSError:
        return False
    return True


def acquire_service_lock(project_dir: Path) -> Path:
    lock_path = service_lock_path(project_dir)
    current_pid = os.getpid()
    cleanup_stale_service_lock(project_dir)
    payload = read_service_lock(project_dir)
    if payload:
        existing_pid = int(payload.get("pid", 0) or 0)
        if existing_pid and existing_pid != current_pid and is_process_alive(existing_pid):
            raise RoleplayOutletAlreadyRunningError(existing_pid)
    write_json(
        lock_path,
        {
            "pid": current_pid,
            "startedAt": datetime.now().isoformat(timespec="seconds"),
        },
    )
    return lock_path


def release_service_lock(lock_path: Path) -> None:
    if not lock_path.exists():
        return
    payload = read_json_file(lock_path) or {}
    owner_pid = int(payload.get("pid", 0) or 0)
    if owner_pid and owner_pid != os.getpid() and is_process_alive(owner_pid):
        return
    try:
        lock_path.unlink()
    except OSError:
        pass


def request_service_stop(project_dir: Path, *, reason: str = "manual stop") -> None:
    write_json(
        service_stop_request_path(project_dir),
        {
            "requestedAt": datetime.now().isoformat(timespec="seconds"),
            "reason": str(reason or "").strip() or "manual stop",
        },
    )


def clear_service_stop_request(project_dir: Path) -> None:
    path = service_stop_request_path(project_dir)
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass


def read_service_stop_request(project_dir: Path) -> dict[str, Any] | None:
    return read_json_file(service_stop_request_path(project_dir))


def read_service_status(project_dir: Path) -> dict[str, Any] | None:
    return read_json_file(service_status_path(project_dir))


def write_service_status(project_dir: Path, *, status: str, stage: str = "", **extra: Any) -> None:
    payload = {
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "stage": stage,
        **{key: value for key, value in extra.items() if value not in ("", None)},
    }
    write_json(service_status_path(project_dir), payload)


def append_service_event(project_dir: Path, payload: dict[str, Any]) -> None:
    event = {"recordedAt": datetime.now().isoformat(timespec="seconds"), **payload}
    path = service_events_path(project_dir)
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
