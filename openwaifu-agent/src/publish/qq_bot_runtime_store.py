from __future__ import annotations

import ctypes
import json
import os
import threading
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import ensure_dir, write_json

from .qq_bot_job_queue import QQBotJobQueue
from .state import publish_state_root


class QQGenerateServiceAlreadyRunningError(RuntimeError):
    def __init__(self, pid: int):
        super().__init__(f"QQ generate service is already running with pid {pid}.")
        self.pid = int(pid)


class ServiceShutdownRequested(RuntimeError):
    pass


def qq_bot_generate_service_state_root(project_dir: Path) -> Path:
    return ensure_dir(publish_state_root(project_dir) / "qq_bot_generate_service")


def _service_lock_path(project_dir: Path) -> Path:
    return qq_bot_generate_service_state_root(project_dir) / "service.lock.json"


def _service_stop_request_path(project_dir: Path) -> Path:
    return qq_bot_generate_service_state_root(project_dir) / "stop.request.json"


def read_service_lock(project_dir: Path) -> dict[str, Any] | None:
    lock_path = _service_lock_path(project_dir)
    if not lock_path.exists():
        return None
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def read_service_pid(project_dir: Path) -> int:
    payload = read_service_lock(project_dir) or {}
    try:
        return int(payload.get("pid", 0) or 0)
    except Exception:
        return 0


def _is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        process_query_limited_information = 0x1000
        synchronize = 0x00100000
        still_active = 259
        access_mask = process_query_limited_information | synchronize
        try:
            kernel32 = ctypes.windll.kernel32
            open_process = kernel32.OpenProcess
            open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            open_process.restype = wintypes.HANDLE
            get_exit_code_process = kernel32.GetExitCodeProcess
            get_exit_code_process.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            get_exit_code_process.restype = wintypes.BOOL
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = [wintypes.HANDLE]
            close_handle.restype = wintypes.BOOL

            handle = open_process(access_mask, False, int(pid))
            if not handle:
                return False
            try:
                exit_code = wintypes.DWORD()
                if not get_exit_code_process(handle, ctypes.byref(exit_code)):
                    return False
                return int(exit_code.value) == still_active
            finally:
                close_handle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    except BaseException:
        return False
    return True


def is_service_running(project_dir: Path) -> bool:
    pid = read_service_pid(project_dir)
    return bool(pid and _is_process_alive(pid))


def cleanup_stale_service_lock(project_dir: Path) -> bool:
    lock_path = _service_lock_path(project_dir)
    pid = read_service_pid(project_dir)
    if not lock_path.exists():
        return False
    if pid and _is_process_alive(pid):
        return False
    try:
        lock_path.unlink()
    except OSError:
        return False
    return True


def request_service_stop(project_dir: Path, *, reason: str = "manual stop") -> Path:
    path = _service_stop_request_path(project_dir)
    write_json(
        path,
        {
            "requestedAt": datetime.now().isoformat(timespec="seconds"),
            "reason": str(reason or "").strip() or "manual stop",
        },
    )
    return path


def clear_service_stop_request(project_dir: Path) -> None:
    path = _service_stop_request_path(project_dir)
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass


def read_service_stop_request(project_dir: Path) -> dict[str, Any] | None:
    path = _service_stop_request_path(project_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"reason": "unknown"}
    return payload if isinstance(payload, dict) else {"reason": "unknown"}


def acquire_service_lock(project_dir: Path) -> Path:
    lock_path = _service_lock_path(project_dir)
    current_pid = os.getpid()
    if lock_path.exists():
        try:
            payload = json.loads(lock_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        try:
            existing_pid = int(payload.get("pid", 0) or 0)
        except Exception:
            existing_pid = 0
        if existing_pid and existing_pid != current_pid and _is_process_alive(existing_pid):
            raise QQGenerateServiceAlreadyRunningError(existing_pid)
        try:
            lock_path.unlink()
        except OSError:
            pass
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
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    try:
        owner_pid = int(payload.get("pid", 0) or 0)
    except Exception:
        owner_pid = 0
    current_pid = os.getpid()
    if owner_pid and owner_pid != current_pid and _is_process_alive(owner_pid):
        return
    try:
        lock_path.unlink()
    except OSError:
        pass


def read_service_status(project_dir: Path) -> dict[str, Any] | None:
    status_path = qq_bot_generate_service_state_root(project_dir) / "latest_status.json"
    if not status_path.exists():
        return None
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def load_latest_known_user_openid(project_dir: Path) -> str:
    state_path = publish_state_root(project_dir) / "qq_bot_gateway" / "latest_user_openid.json"
    if state_path.exists():
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            value = str(payload.get("userOpenId", "")).strip()
            if value:
                return value
        except Exception:
            pass

    env_path = project_dir / ".env"
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if not line.startswith("QQ_BOT_USER_OPENID="):
                    continue
                return line.partition("=")[2].strip().strip('"').strip("'")
        except Exception:
            return ""
    return ""


def write_service_status(project_dir: Path, payload: dict[str, Any]) -> Path:
    status_path = qq_bot_generate_service_state_root(project_dir) / "latest_status.json"
    write_json(status_path, payload)
    return status_path


def append_service_event(project_dir: Path, payload: dict[str, Any]) -> None:
    log_path = qq_bot_generate_service_state_root(project_dir) / "service_events.jsonl"
    ensure_dir(log_path.parent)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_stage_status(
    *,
    project_dir: Path,
    status: str,
    stage: str = "",
    user_openid: str = "",
    source_message_id: str = "",
    run_id: str = "",
    queued_count: int = 0,
    queue_position: int = 0,
    queue_size: int = 0,
    error: str = "",
    failed_run_root: str = "",
    generated_image_path: str = "",
    publish_package_path: str = "",
) -> None:
    payload: dict[str, Any] = {
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "stage": stage,
        "queuedCount": queued_count,
    }
    if user_openid:
        payload["userOpenId"] = user_openid
    if source_message_id:
        payload["sourceMessageId"] = source_message_id
    if run_id:
        payload["runId"] = run_id
    if error:
        payload["error"] = error
    if queue_position:
        payload["queuePosition"] = int(queue_position)
    if queue_size:
        payload["queueSize"] = int(queue_size)
    if failed_run_root:
        payload["failedRunRoot"] = failed_run_root
    if generated_image_path:
        payload["generatedImagePath"] = generated_image_path
    if publish_package_path:
        payload["publishPackagePath"] = publish_package_path
    write_service_status(project_dir, payload)


def snapshot_service_runtime(service_runtime: dict[str, Any], service_runtime_lock: threading.Lock) -> dict[str, Any]:
    with service_runtime_lock:
        return {
            "activeRunId": service_runtime.get("activeRunId"),
            "activeUserOpenId": service_runtime.get("activeUserOpenId", ""),
            "activeSourceMessageId": service_runtime.get("activeSourceMessageId", ""),
            "currentStage": service_runtime.get("currentStage", ""),
            "reserved": bool(service_runtime.get("reserved")),
        }


def mark_shutdown_requested(
    *,
    project_dir: Path,
    service_runtime: dict[str, Any],
    service_runtime_lock: threading.Lock,
    job_queue: QQBotJobQueue,
    reason: str = "",
) -> None:
    runtime_snapshot = snapshot_service_runtime(service_runtime, service_runtime_lock)
    append_service_event(
        project_dir,
        {
            "recordedAt": datetime.now().isoformat(timespec="seconds"),
            "type": "service_stop_requested",
            "runId": str(runtime_snapshot.get("activeRunId") or "").strip(),
            "stage": str(runtime_snapshot.get("currentStage") or "").strip(),
            "reason": str(reason or "").strip(),
        },
    )
    write_stage_status(
        project_dir=project_dir,
        status="stopping",
        stage=str(runtime_snapshot.get("currentStage") or "").strip() or "shutdown_requested",
        user_openid=str(runtime_snapshot.get("activeUserOpenId") or "").strip(),
        source_message_id=str(runtime_snapshot.get("activeSourceMessageId") or "").strip(),
        run_id=str(runtime_snapshot.get("activeRunId") or "").strip(),
        queued_count=job_queue.pending_count(),
        error=str(reason or "").strip(),
    )
