from __future__ import annotations

import json
import os
import queue
import threading
import time
import ctypes
from collections import deque
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import websocket
from websocket._exceptions import WebSocketConnectionClosedException, WebSocketTimeoutException

from io_utils import ensure_dir, write_json
from product_pipeline import run_full_product_pipeline, run_scene_draft_full_pipeline
from runtime_layout import create_run_bundle, sanitize_segment, update_latest

from .qq_bot_client import (
    fetch_app_access_token,
    load_qq_bot_message_config,
    resolve_qq_bot_credentials,
    send_text_message,
)
from .qq_bot_gateway import (
    QQ_BOT_C2C_SERVICE_INTENTS,
    build_gateway_heartbeat_payload,
    build_gateway_identify_payload,
    fetch_gateway_info,
    persist_user_openid,
    save_gateway_event,
    save_gateway_status,
)
from .qq_bot_identity import extract_user_openid
from .qq_bot_private_ui import (
    MODE_DEVELOPER,
    MODE_EXPERIENCE,
    build_busy_text as build_busy_text_ui,
    build_scene_draft_busy_text,
    build_developer_pending_text,
    build_developer_input_text,
    build_developer_input_received_text,
    build_developer_continue_hint_text,
    build_failed_text as build_failed_text_ui,
    build_help_text as build_help_text_ui,
    build_mode_switched_text,
    build_started_text as build_started_text_ui,
    build_status_text_from_payload,
    build_unknown_command_text,
    build_wrong_mode_command_text,
    normalize_private_mode,
)
from .qq_bot_private_state import (
    DEFAULT_PENDING_ACTION,
    PENDING_ACTION_SCENE_DRAFT,
    load_private_user_state,
    set_private_user_mode,
    set_private_user_pending_action,
)
from .qq_bot_scene_draft import parse_scene_draft_message, persist_scene_draft_message
from .state import publish_state_root


DEFAULT_TRIGGER_COMMAND = "生成"
DEFAULT_HELP_COMMAND = "帮助"
DEFAULT_STATUS_COMMAND = "状态"
DEFAULT_EXPERIENCE_MODE_COMMAND = "体验者模式"
DEFAULT_DEVELOPER_MODE_COMMAND = "开发者模式"
DEFAULT_DEVELOPER_SCENE_COMMAND = "注入场景稿"
COMMAND_ALIASES = {
    DEFAULT_TRIGGER_COMMAND: {DEFAULT_TRIGGER_COMMAND, "/g"},
    DEFAULT_STATUS_COMMAND: {DEFAULT_STATUS_COMMAND, "/s"},
    DEFAULT_HELP_COMMAND: {DEFAULT_HELP_COMMAND, "/h"},
    DEFAULT_DEVELOPER_MODE_COMMAND: {DEFAULT_DEVELOPER_MODE_COMMAND, "/d"},
    DEFAULT_EXPERIENCE_MODE_COMMAND: {DEFAULT_EXPERIENCE_MODE_COMMAND, "/e"},
    DEFAULT_DEVELOPER_SCENE_COMMAND: {DEFAULT_DEVELOPER_SCENE_COMMAND, "/i"},
}
DEFAULT_WS_RECV_TIMEOUT_SECONDS = 2.0
DEFAULT_RECONNECT_DELAY_SECONDS = 3.0
MAX_HANDLED_MESSAGE_IDS = 500
_COMMAND_WRAPPING_QUOTES = "\"'“”‘’「」『』`"
_COMMAND_TRAILING_PUNCTUATION = "。！？!?，,、；;：:~～…"


class QQGenerateServiceAlreadyRunningError(RuntimeError):
    def __init__(self, pid: int):
        super().__init__(f"QQ generate service is already running with pid {pid}.")
        self.pid = int(pid)


class _ServiceShutdownRequested(RuntimeError):
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


def _acquire_service_lock(project_dir: Path) -> Path:
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


def _release_service_lock(lock_path: Path) -> None:
    if not lock_path.exists():
        return
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if int(payload.get("pid", 0) or 0) != os.getpid():
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
        return json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_latest_known_user_openid(project_dir: Path) -> str:
    latest_path = publish_state_root(project_dir) / "qq_bot_gateway" / "latest_user_openid.json"
    if latest_path.exists():
        try:
            payload = json.loads(latest_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        user_openid = str(payload.get("userOpenId", "")).strip()
        if user_openid:
            return user_openid

    env_path = project_dir / ".env"
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8-sig").splitlines():
                if line.strip().startswith("QQ_BOT_USER_OPENID="):
                    _, _, value = line.partition("=")
                    user_openid = value.strip()
                    if user_openid:
                        return user_openid
        except Exception:
            return ""
    return ""


def _write_service_status(project_dir: Path, payload: dict[str, Any]) -> Path:
    status_path = qq_bot_generate_service_state_root(project_dir) / "latest_status.json"
    write_json(status_path, payload)
    return status_path


def _append_service_event(project_dir: Path, payload: dict[str, Any]) -> None:
    log_path = qq_bot_generate_service_state_root(project_dir) / "service_events.jsonl"
    ensure_dir(log_path.parent)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _write_stage_status(
    *,
    project_dir: Path,
    status: str,
    stage: str = "",
    user_openid: str = "",
    source_message_id: str = "",
    run_id: str = "",
    queued_count: int = 0,
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
    if failed_run_root:
        payload["failedRunRoot"] = failed_run_root
    if generated_image_path:
        payload["generatedImagePath"] = generated_image_path
    if publish_package_path:
        payload["publishPackagePath"] = publish_package_path
    _write_service_status(project_dir, payload)


def _snapshot_service_runtime(service_runtime: dict[str, Any], service_runtime_lock: threading.Lock) -> dict[str, Any]:
    with service_runtime_lock:
        return {
            "activeRunId": service_runtime.get("activeRunId"),
            "activeUserOpenId": service_runtime.get("activeUserOpenId", ""),
            "activeSourceMessageId": service_runtime.get("activeSourceMessageId", ""),
            "currentStage": service_runtime.get("currentStage", ""),
            "reserved": bool(service_runtime.get("reserved")),
        }


def _mark_shutdown_requested(
    *,
    project_dir: Path,
    service_runtime: dict[str, Any],
    service_runtime_lock: threading.Lock,
    task_queue: queue.Queue[dict[str, Any]],
    reason: str = "",
) -> None:
    runtime_snapshot = _snapshot_service_runtime(service_runtime, service_runtime_lock)
    _append_service_event(
        project_dir,
        {
            "recordedAt": datetime.now().isoformat(timespec="seconds"),
            "type": "service_stop_requested",
            "runId": str(runtime_snapshot.get("activeRunId") or "").strip(),
            "stage": str(runtime_snapshot.get("currentStage") or "").strip(),
            "reason": str(reason or "").strip(),
        },
    )
    _write_stage_status(
        project_dir=project_dir,
        status="stopping",
        stage=str(runtime_snapshot.get("currentStage") or "").strip() or "shutdown_requested",
        user_openid=str(runtime_snapshot.get("activeUserOpenId") or "").strip(),
        source_message_id=str(runtime_snapshot.get("activeSourceMessageId") or "").strip(),
        run_id=str(runtime_snapshot.get("activeRunId") or "").strip(),
        queued_count=task_queue.qsize(),
        error=str(reason or "").strip(),
    )


def _recv_gateway_payload(ws: websocket.WebSocket, *, timeout_seconds: float) -> tuple[str | None, dict | None]:
    deadline = time.time() + timeout_seconds
    previous_timeout = ws.gettimeout()
    try:
        while True:
            remaining = max(deadline - time.time(), 0.0)
            if remaining <= 0:
                return None, None
            ws.settimeout(remaining)
            try:
                raw_message = ws.recv()
            except WebSocketTimeoutException:
                return None, None
            text = str(raw_message or "").strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            return text, payload
    finally:
        ws.settimeout(previous_timeout)


def _connect_gateway(credentials: dict, token_response: dict) -> tuple[websocket.WebSocket, dict]:
    gateway_info = fetch_gateway_info(
        app_id=credentials["appId"],
        access_token=str(token_response["access_token"]),
        api_base_url=credentials["apiBaseUrl"],
        timeout_ms=credentials["timeoutMs"],
    )
    ws = websocket.create_connection(
        str(gateway_info["url"]),
        timeout=max(credentials["timeoutMs"], 1000) / 1000.0,
    )
    hello_payload = json.loads(ws.recv())
    heartbeat_interval = int(hello_payload.get("d", {}).get("heartbeat_interval", 0))
    if heartbeat_interval <= 0:
        ws.close()
        raise RuntimeError(f"QQ bot gateway hello payload missing heartbeat interval: {hello_payload}")

    state = {"seq": None, "running": True}

    def _heartbeat_loop() -> None:
        while state["running"]:
            time.sleep(heartbeat_interval / 1000.0)
            if not state["running"]:
                return
            try:
                ws.send(json.dumps(build_gateway_heartbeat_payload(state["seq"]), ensure_ascii=False))
            except Exception:
                return

    threading.Thread(target=_heartbeat_loop, daemon=True).start()

    identify_payload = build_gateway_identify_payload(
        access_token=str(token_response["access_token"]),
        intents=QQ_BOT_C2C_SERVICE_INTENTS,
    )
    ws.send(json.dumps(identify_payload, ensure_ascii=False))
    return ws, {
        "gatewayInfo": gateway_info,
        "helloPayload": hello_payload,
        "identifyPayload": identify_payload,
        "state": state,
    }


def _user_mode(project_dir: Path, user_openid: str) -> str:
    return normalize_private_mode(load_private_user_state(project_dir, user_openid).get("mode", MODE_EXPERIENCE))


def _build_help_text(trigger_command: str, help_command: str, *, mode: str = MODE_EXPERIENCE) -> str:
    return build_help_text_ui(trigger_command, help_command, DEFAULT_STATUS_COMMAND, mode=mode)


def _load_status_payload(project_dir: Path) -> dict[str, Any] | None:
    status_path = qq_bot_generate_service_state_root(project_dir) / "latest_status.json"
    if not status_path.exists():
        return None
    return json.loads(status_path.read_text(encoding="utf-8"))


def _build_busy_text(project_dir: Path) -> str:
    status_payload = _load_status_payload(project_dir)
    status_text = build_status_text_from_payload(status_payload) if status_payload else ""
    return build_busy_text_ui(status_text)


def _build_busy_text_for_mode(project_dir: Path, *, mode: str) -> str:
    status_payload = _load_status_payload(project_dir)
    status_text = build_status_text_from_payload(status_payload, mode=mode) if status_payload else ""
    return build_busy_text_ui(status_text, mode=mode)


def _build_scene_draft_busy_reply(project_dir: Path) -> str:
    status_payload = _load_status_payload(project_dir)
    status_text = build_status_text_from_payload(status_payload, mode=MODE_DEVELOPER) if status_payload else ""
    return build_scene_draft_busy_text(status_text)


def _build_started_text(*, mode: str = MODE_EXPERIENCE) -> str:
    return build_started_text_ui(mode=mode)


def _build_failed_text(exc: Exception) -> str:
    return build_failed_text_ui(exc)


def _build_status_text(project_dir: Path, *, mode: str = MODE_EXPERIENCE) -> str:
    payload = _load_status_payload(project_dir)
    if payload is None:
        return "生成服务还没有状态记录。"
    return build_status_text_from_payload(payload, mode=mode)


def _service_is_busy(service_runtime: dict[str, Any], service_runtime_lock: threading.Lock) -> bool:
    snapshot = _snapshot_service_runtime(service_runtime, service_runtime_lock)
    return bool(snapshot.get("activeRunId")) or bool(snapshot.get("reserved"))


def _is_non_interrupting_command(kind: str) -> bool:
    return str(kind or "").strip() in {
        "help",
        "status",
        "wrong_mode_command",
        "same_mode_guidance",
        "unknown",
        "awaiting_scene_draft",
        "invalid_scene_draft",
        "scene_draft_submission",
    }


def _is_interrupting_command(kind: str) -> bool:
    return str(kind or "").strip() in {"switch_mode", "developer_scene_prompt", "trigger_generation"}


def _should_reply_busy_once(
    service_runtime: dict[str, Any],
    service_runtime_lock: threading.Lock,
    *,
    user_openid: str,
) -> bool:
    with service_runtime_lock:
        busy_notice_users = service_runtime.setdefault("busyNoticeUsers", set())
        if user_openid in busy_notice_users:
            return False
        busy_notice_users.add(user_openid)
        return True


def _clear_busy_reply_tracking(service_runtime: dict[str, Any], service_runtime_lock: threading.Lock) -> None:
    with service_runtime_lock:
        service_runtime["busyNoticeUsers"] = set()


def _request_task_interrupt(
    service_runtime: dict[str, Any],
    service_runtime_lock: threading.Lock,
    *,
    reason: str,
) -> bool:
    with service_runtime_lock:
        busy = bool(service_runtime.get("activeRunId")) or bool(service_runtime.get("reserved"))
        if not busy:
            return False
        if service_runtime.get("activeRunId"):
            service_runtime["interruptRequested"] = True
            service_runtime["interruptReason"] = str(reason or "").strip() or "interrupted by command"
        return True


def _is_interrupt_requested(service_runtime: dict[str, Any], service_runtime_lock: threading.Lock) -> bool:
    with service_runtime_lock:
        return bool(service_runtime.get("interruptRequested"))


def _replace_queued_task(task_queue: queue.Queue[dict[str, Any]], task: dict[str, Any] | None) -> None:
    while True:
        try:
            task_queue.get_nowait()
            task_queue.task_done()
        except queue.Empty:
            break
    if task is not None:
        task_queue.put_nowait(task)


def _build_full_generation_task(
    *,
    user_openid: str,
    source_message_id: str = "",
    event_id: str = "",
) -> dict[str, Any]:
    return {
        "userOpenId": str(user_openid).strip(),
        "sourceMessageId": str(source_message_id).strip(),
        "replyEventId": str(event_id).strip(),
        "taskType": "full_generation",
    }


def _replace_or_cancel_busy_task(
    *,
    task_queue: queue.Queue[dict[str, Any]],
    service_runtime: dict[str, Any],
    service_runtime_lock: threading.Lock,
    replacement_task: dict[str, Any] | None,
    reason: str,
) -> bool:
    requested = _request_task_interrupt(
        service_runtime,
        service_runtime_lock,
        reason=reason,
    )
    if not requested:
        return False

    with service_runtime_lock:
        has_active_run = bool(service_runtime.get("activeRunId"))
        if not has_active_run:
            service_runtime["reserved"] = replacement_task is not None
            service_runtime["interruptRequested"] = False
            service_runtime["interruptReason"] = ""

    _replace_queued_task(task_queue, replacement_task)
    return True


def _normalize_message_text(content: str) -> str:
    return str(content or "").replace("\u3000", " ").strip()


def _canonicalize_command_text(content: str) -> str:
    normalized = _normalize_message_text(content)
    if not normalized:
        return ""

    previous = None
    current = normalized
    while previous != current:
        previous = current
        current = current.strip()
        if len(current) >= 2 and current[0] in _COMMAND_WRAPPING_QUOTES and current[-1] in _COMMAND_WRAPPING_QUOTES:
            current = current[1:-1].strip()
        while current and current[-1] in _COMMAND_TRAILING_PUNCTUATION:
            current = current[:-1].rstrip()
    return current


def _matches_command_alias(command_text: str, canonical_command: str, *extra_aliases: str) -> bool:
    allowed = set(COMMAND_ALIASES.get(canonical_command, {canonical_command}))
    allowed.update(str(alias or "").strip() for alias in extra_aliases if str(alias or "").strip())
    return command_text in allowed


def _is_known_command_alias(command_text: str, *extra_aliases: str) -> bool:
    if not command_text:
        return False
    for canonical_command in COMMAND_ALIASES:
        if _matches_command_alias(command_text, canonical_command, *extra_aliases):
            return True
    return False


def _mask_user_openid(user_openid: str) -> str:
    text = str(user_openid or "").strip()
    if not text:
        return "unknown"
    if len(text) <= 8:
        return text
    return f"{text[:4]}...{text[-4:]}"


def _emit_key_log(log: Callable[[str], None] | None, message: str) -> None:
    if log is None:
        return
    log(f"[qq-generate] {message}")


def _remember_handled_message(
    source_message_id: str,
    handled_message_ids: set[str],
    handled_message_order: deque[str],
) -> None:
    if not source_message_id or source_message_id in handled_message_ids:
        return
    handled_message_ids.add(source_message_id)
    handled_message_order.append(source_message_id)
    while len(handled_message_order) > MAX_HANDLED_MESSAGE_IDS:
        stale_message_id = handled_message_order.popleft()
        handled_message_ids.discard(stale_message_id)


def _interpret_private_message(
    *,
    content: str,
    user_mode: str,
    pending_action: str,
    status_text: str,
    trigger_command: str = DEFAULT_TRIGGER_COMMAND,
    help_command: str = DEFAULT_HELP_COMMAND,
    status_command: str = DEFAULT_STATUS_COMMAND,
) -> dict[str, Any]:
    normalized_content = _normalize_message_text(content)
    command_text = _canonicalize_command_text(content)
    resolved_mode = normalize_private_mode(user_mode)
    resolved_pending_action = str(pending_action or "").strip()

    if _matches_command_alias(command_text, DEFAULT_HELP_COMMAND, help_command):
        return {
            "kind": "help",
            "replyText": build_help_text_ui(
                trigger_command,
                help_command,
                status_command,
                mode=resolved_mode,
            ),
            "nextMode": resolved_mode,
            "nextPendingAction": resolved_pending_action,
        }
    if _matches_command_alias(command_text, DEFAULT_STATUS_COMMAND, status_command):
        return {
            "kind": "status",
            "replyText": status_text,
            "nextMode": resolved_mode,
            "nextPendingAction": resolved_pending_action,
        }
    if _matches_command_alias(command_text, DEFAULT_DEVELOPER_MODE_COMMAND):
        if resolved_mode == MODE_DEVELOPER:
            return {
                "kind": "same_mode_guidance",
                "replyText": (
                    build_developer_input_text()
                    if resolved_pending_action == PENDING_ACTION_SCENE_DRAFT
                    else build_mode_switched_text(MODE_DEVELOPER)
                ),
                "nextMode": MODE_DEVELOPER,
                "nextPendingAction": resolved_pending_action,
            }
        return {
            "kind": "switch_mode",
            "replyText": build_mode_switched_text(MODE_DEVELOPER),
            "nextMode": MODE_DEVELOPER,
            "nextPendingAction": DEFAULT_PENDING_ACTION,
        }
    if _matches_command_alias(command_text, DEFAULT_EXPERIENCE_MODE_COMMAND):
        if resolved_mode == MODE_EXPERIENCE:
            return {
                "kind": "same_mode_guidance",
                "replyText": build_mode_switched_text(MODE_EXPERIENCE),
                "nextMode": MODE_EXPERIENCE,
                "nextPendingAction": resolved_pending_action,
            }
        return {
            "kind": "switch_mode",
            "replyText": build_mode_switched_text(MODE_EXPERIENCE),
            "nextMode": MODE_EXPERIENCE,
            "nextPendingAction": DEFAULT_PENDING_ACTION,
        }
    if resolved_mode == MODE_DEVELOPER and _matches_command_alias(command_text, DEFAULT_DEVELOPER_SCENE_COMMAND):
        return {
            "kind": "developer_scene_prompt",
            "replyText": build_developer_input_text(),
            "nextMode": MODE_DEVELOPER,
            "nextPendingAction": PENDING_ACTION_SCENE_DRAFT,
        }
    if resolved_mode == MODE_EXPERIENCE and _matches_command_alias(command_text, DEFAULT_TRIGGER_COMMAND, trigger_command):
        return {
            "kind": "trigger_generation",
            "replyText": build_started_text_ui(mode=resolved_mode),
            "nextMode": resolved_mode,
            "nextPendingAction": resolved_pending_action,
        }
    if resolved_mode == MODE_EXPERIENCE and _matches_command_alias(command_text, DEFAULT_DEVELOPER_SCENE_COMMAND):
        return {
            "kind": "wrong_mode_command",
            "replyText": build_wrong_mode_command_text(
                current_mode=resolved_mode,
                trigger_command=trigger_command,
                help_command=help_command,
                status_command=status_command,
            ),
            "nextMode": resolved_mode,
            "nextPendingAction": resolved_pending_action,
        }
    if resolved_mode == MODE_DEVELOPER and _matches_command_alias(command_text, DEFAULT_TRIGGER_COMMAND, trigger_command):
        return {
            "kind": "wrong_mode_command",
            "replyText": build_wrong_mode_command_text(
                current_mode=resolved_mode,
                trigger_command=trigger_command,
                help_command=help_command,
                status_command=status_command,
            ),
            "nextMode": resolved_mode,
            "nextPendingAction": resolved_pending_action,
        }
    if command_text and _is_known_command_alias(command_text, trigger_command, help_command, status_command):
        return {
            "kind": "unknown",
            "replyText": build_unknown_command_text(
                trigger_command,
                help_command,
                status_command,
                mode=resolved_mode,
            ),
            "nextMode": resolved_mode,
            "nextPendingAction": resolved_pending_action,
        }
    if resolved_pending_action == PENDING_ACTION_SCENE_DRAFT:
        if not normalized_content:
            return {
                "kind": "awaiting_scene_draft",
                "replyText": build_developer_pending_text(),
                "nextMode": resolved_mode,
                "nextPendingAction": PENDING_ACTION_SCENE_DRAFT,
            }
        try:
            scene_draft = parse_scene_draft_message(normalized_content)
        except Exception as exc:
            return {
                "kind": "invalid_scene_draft",
                "replyText": "\n".join(
                    [
                        "场景设计稿格式不正确",
                        "",
                        str(exc),
                        "",
                        build_developer_input_text(),
                    ]
                ),
                "nextMode": resolved_mode,
                "nextPendingAction": PENDING_ACTION_SCENE_DRAFT,
            }
        return {
            "kind": "scene_draft_submission",
            "replyText": build_developer_input_received_text(scene_draft.get("scenePremiseZh", "")),
            "sceneDraft": scene_draft,
            "nextMode": resolved_mode,
            "nextPendingAction": PENDING_ACTION_SCENE_DRAFT,
        }
    return {
        "kind": "unknown",
        "replyText": build_unknown_command_text(
            trigger_command,
            help_command,
            status_command,
            mode=resolved_mode,
        ),
        "nextMode": resolved_mode,
        "nextPendingAction": resolved_pending_action,
    }


def _scene_draft_source_meta(scene_draft_path: Path, *, user_openid: str) -> dict[str, Any]:
    return {
        "sceneDraftPath": str(scene_draft_path),
        "sourceType": "qq_bot_developer_mode",
        "userOpenId": str(user_openid).strip(),
    }


def _build_dynamic_publish_target(user_openid: str) -> dict[str, Any]:
    return {
        "targetId": "qq_bot_user_dynamic",
        "adapter": "qq_bot_user",
        "displayName": "QQ Bot User Dynamic",
        "scene": "user",
        "targetOpenId": str(user_openid).strip(),
        "configPath": "config/publish/qq_bot_message.json",
        "userOpenIdEnvName": "QQ_BOT_USER_OPENID",
    }


def _build_dynamic_reply_target(
    *,
    user_openid: str,
    source_message_id: str = "",
    reply_message_seq: int = 0,
    reply_event_id: str = "",
) -> dict[str, Any]:
    target = _build_dynamic_publish_target(user_openid)
    if source_message_id:
        target["replyMessageId"] = source_message_id
    if reply_message_seq > 0:
        target["replyMessageSeq"] = reply_message_seq
    if reply_event_id:
        target["replyEventId"] = reply_event_id
    return target


def _run_generation_task(
    *,
    project_dir: Path,
    bundle,
    task: dict[str, Any],
    log: Callable[[str], None] | None,
    should_abort: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    user_openid = str(task["userOpenId"]).strip()
    source_message_id = str(task.get("sourceMessageId", "")).strip()
    reply_event_id = str(task.get("replyEventId", "")).strip()
    publish_targets = [
        _build_dynamic_reply_target(
            user_openid=user_openid,
            source_message_id=source_message_id,
            reply_message_seq=2 if source_message_id else 0,
            reply_event_id=reply_event_id,
        )
    ]
    task_type = str(task.get("taskType", "full_generation")).strip()
    if task_type == "scene_draft_to_image":
        return run_scene_draft_full_pipeline(
            project_dir,
            bundle,
            scene_draft=dict(task["sceneDraft"]),
            source_meta=_scene_draft_source_meta(Path(str(task["sceneDraftPath"])), user_openid=user_openid),
            log=log,
            explicit_publish_targets=publish_targets,
            should_abort=should_abort,
        )
    return run_full_product_pipeline(
        project_dir,
        bundle,
        log=log,
        explicit_publish_targets=publish_targets,
        should_abort=should_abort,
    )


def _reserve_generation_slot(service_runtime: dict[str, Any], service_runtime_lock: threading.Lock) -> bool:
    with service_runtime_lock:
        busy = bool(service_runtime["activeRunId"]) or bool(service_runtime["reserved"])
        if busy:
            return False
        service_runtime["reserved"] = True
        return True


def _enqueue_generation_task(
    *,
    project_dir: Path,
    task_queue: queue.Queue[dict[str, Any]],
    service_runtime: dict[str, Any],
    service_runtime_lock: threading.Lock,
    user_openid: str,
    source_message_id: str = "",
    reply_event_id: str = "",
    task_type: str = "full_generation",
    scene_draft: dict[str, Any] | None = None,
    scene_draft_path: Path | None = None,
) -> bool:
    if not _reserve_generation_slot(service_runtime, service_runtime_lock):
        return False
    task: dict[str, Any] = {
        "userOpenId": user_openid,
        "sourceMessageId": source_message_id,
        "replyEventId": reply_event_id,
        "taskType": task_type,
    }
    if scene_draft is not None:
        task["sceneDraft"] = dict(scene_draft)
    if scene_draft_path is not None:
        task["sceneDraftPath"] = str(scene_draft_path)
    task_queue.put(task)
    return True


def _reply_text_for_user(
    *,
    project_dir: Path,
    credentials: dict[str, Any],
    user_openid: str,
    text_content: str,
    source_message_id: str = "",
    msg_seq: int = 0,
    event_id: str = "",
) -> dict[str, Any]:
    token_response = fetch_app_access_token(
        app_id=credentials["appId"],
        app_secret=credentials["appSecret"],
        access_token_url=credentials["accessTokenUrl"],
        timeout_ms=credentials["timeoutMs"],
    )
    return send_text_message(
        access_token=str(token_response["access_token"]),
        api_base_url=credentials["apiBaseUrl"],
        scene="user",
        target_openid=user_openid,
        content=text_content,
        timeout_ms=credentials["timeoutMs"],
        msg_id=source_message_id,
        msg_seq=msg_seq,
        event_id=event_id,
    )


def _send_startup_guidance_if_possible(
    *,
    project_dir: Path,
    credentials: dict[str, Any],
    trigger_command: str,
    help_command: str,
    status_command: str,
    log: Callable[[str], None] | None,
) -> bool:
    user_openid = _load_latest_known_user_openid(project_dir)
    if not user_openid:
        _emit_key_log(log, "启动后未找到已知用户，暂不主动推送指引。")
        return False

    user_mode = _user_mode(project_dir, user_openid)
    help_text = build_help_text_ui(trigger_command, help_command, status_command, mode=user_mode)
    try:
        _reply_text_for_user(
            project_dir=project_dir,
            credentials=credentials,
            user_openid=user_openid,
            text_content=help_text,
        )
    except Exception as exc:
        _append_service_event(
            project_dir,
            {
                "recordedAt": datetime.now().isoformat(timespec="seconds"),
                "type": "startup_guidance_failed",
                "userOpenId": user_openid,
                "error": str(exc),
            },
        )
        _emit_key_log(log, f"启动指引推送失败 user={_mask_user_openid(user_openid)} error={str(exc)[:120]}")
        return False

    _append_service_event(
        project_dir,
        {
            "recordedAt": datetime.now().isoformat(timespec="seconds"),
            "type": "startup_guidance_sent",
            "userOpenId": user_openid,
            "mode": user_mode,
        },
    )
    _emit_key_log(log, f"启动指引已推送给 user={_mask_user_openid(user_openid)} mode={user_mode}")
    return True


def _current_status_payload(project_dir: Path, task_queue: queue.Queue[dict[str, Any]]) -> dict[str, Any]:
    return _load_status_payload(project_dir) or {
        "status": "idle",
        "stage": "waiting_for_trigger",
        "queuedCount": task_queue.qsize(),
    }


def _reply_busy(
    *,
    project_dir: Path,
    credentials: dict[str, Any],
    user_openid: str,
    mode: str = MODE_EXPERIENCE,
    source_message_id: str = "",
    msg_seq: int = 0,
    event_id: str = "",
) -> dict[str, Any]:
    return _reply_text_for_user(
        project_dir=project_dir,
        credentials=credentials,
        user_openid=user_openid,
        text_content=_build_busy_text_for_mode(project_dir, mode=mode),
        source_message_id=source_message_id,
        msg_seq=msg_seq,
        event_id=event_id,
    )


def _accept_full_generation(
    *,
    project_dir: Path,
    task_queue: queue.Queue[dict[str, Any]],
    service_runtime: dict[str, Any],
    service_runtime_lock: threading.Lock,
    user_openid: str,
    source_message_id: str = "",
    event_id: str = "",
) -> bool:
    accepted = _enqueue_generation_task(
        project_dir=project_dir,
        task_queue=task_queue,
        service_runtime=service_runtime,
        service_runtime_lock=service_runtime_lock,
        user_openid=user_openid,
        source_message_id=source_message_id,
        reply_event_id=event_id,
        task_type="full_generation",
    )
    if accepted:
        _write_stage_status(
            project_dir=project_dir,
            status="queued",
            stage="queued_for_generation",
            user_openid=user_openid,
            source_message_id=source_message_id,
            queued_count=task_queue.qsize(),
        )
        _append_service_event(
            project_dir,
            {
                "recordedAt": datetime.now().isoformat(timespec="seconds"),
                "type": "trigger_accepted",
                "userOpenId": user_openid,
                "sourceMessageId": source_message_id,
                "eventId": event_id,
            },
        )
    return accepted


def _accept_scene_draft_generation(
    *,
    project_dir: Path,
    task_queue: queue.Queue[dict[str, Any]],
    service_runtime: dict[str, Any],
    service_runtime_lock: threading.Lock,
    user_openid: str,
    scene_draft: dict[str, Any],
    scene_draft_path: Path,
    source_message_id: str = "",
    event_id: str = "",
) -> bool:
    accepted = _enqueue_generation_task(
        project_dir=project_dir,
        task_queue=task_queue,
        service_runtime=service_runtime,
        service_runtime_lock=service_runtime_lock,
        user_openid=user_openid,
        source_message_id=source_message_id,
        reply_event_id=event_id,
        task_type="scene_draft_to_image",
        scene_draft=scene_draft,
        scene_draft_path=scene_draft_path,
    )
    if accepted:
        _write_stage_status(
            project_dir=project_dir,
            status="queued",
            stage="queued_for_scene_draft_generation",
            user_openid=user_openid,
            source_message_id=source_message_id,
            queued_count=task_queue.qsize(),
        )
        _append_service_event(
            project_dir,
            {
                "recordedAt": datetime.now().isoformat(timespec="seconds"),
                "type": "scene_draft_trigger_accepted",
                "userOpenId": user_openid,
                "sourceMessageId": source_message_id,
                "eventId": event_id,
                "sceneDraftPath": str(scene_draft_path),
            },
        )
    return accepted


def _task_worker(
    *,
    project_dir: Path,
    credentials: dict,
    task_queue: queue.Queue[dict[str, Any]],
    stop_event: threading.Event,
    service_runtime: dict[str, Any],
    service_runtime_lock: threading.Lock,
    log: Callable[[str], None] | None,
) -> None:
    while not stop_event.is_set():
        try:
            task = task_queue.get(timeout=1.0)
        except queue.Empty:
            continue

        user_openid = str(task["userOpenId"]).strip()
        source_message_id = str(task["sourceMessageId"]).strip()
        reply_event_id = str(task.get("replyEventId", "")).strip()
        task_type = str(task.get("taskType", "full_generation")).strip()
        run_prefix = "qqbot_scene" if task_type == "scene_draft_to_image" else "qqbot_generate"
        run_label = f"{run_prefix}_{sanitize_segment(user_openid[:8].lower())}"
        bundle = create_run_bundle(project_dir, "generate", run_label)
        _emit_key_log(
            log,
            f"开始执行任务 runId={bundle.run_id} type={task_type} user={_mask_user_openid(user_openid)}",
        )

        with service_runtime_lock:
            service_runtime["activeRunId"] = bundle.run_id
            service_runtime["activeUserOpenId"] = user_openid
            service_runtime["activeSourceMessageId"] = source_message_id
            service_runtime["currentStage"] = "starting"
            service_runtime["interruptRequested"] = False
            service_runtime["interruptReason"] = ""
            service_runtime["busyNoticeUsers"] = set()

        _write_stage_status(
            project_dir=project_dir,
            status="running",
            stage="starting",
            user_openid=user_openid,
            source_message_id=source_message_id,
            run_id=bundle.run_id,
            queued_count=task_queue.qsize(),
        )

        def _task_log(message: str) -> None:
            with service_runtime_lock:
                service_runtime["currentStage"] = message
                interrupt_requested = bool(service_runtime.get("interruptRequested"))
            _append_service_event(
                project_dir,
                {
                    "recordedAt": datetime.now().isoformat(timespec="seconds"),
                    "type": "generation_log",
                    "runId": bundle.run_id,
                    "message": message,
                },
            )
            _write_stage_status(
                project_dir=project_dir,
                status="running",
                stage=message,
                user_openid=user_openid,
                source_message_id=source_message_id,
                run_id=bundle.run_id,
                queued_count=task_queue.qsize(),
            )
            if log is not None:
                log(message)
            if interrupt_requested:
                raise InterruptedError("Generation interrupted by command.")

        def _should_abort_task() -> bool:
            return _is_interrupt_requested(service_runtime, service_runtime_lock)

        try:
            result = _run_generation_task(
                project_dir=project_dir,
                bundle=bundle,
                task=task,
                log=_task_log,
                should_abort=_should_abort_task,
            )
            summary = result["summary"]
            update_latest(
                project_dir,
                bundle,
                {
                    "runId": bundle.run_id,
                    "creativePackagePath": summary["creativePackagePath"],
                    "socialPostPackagePath": summary["socialPostPackagePath"],
                    "promptPackagePath": summary["promptPackagePath"],
                    "executionPackagePath": summary["executionPackagePath"],
                    "publishPackagePath": summary["publishPackagePath"],
                    "summaryPath": str(bundle.output_dir / "run_summary.json"),
                    "sceneDraftPremiseZh": summary["sceneDraftPremiseZh"],
                },
            )
            _append_service_event(
                project_dir,
                {
                    "recordedAt": datetime.now().isoformat(timespec="seconds"),
                    "type": "generation_completed",
                    "runId": bundle.run_id,
                    "userOpenId": user_openid,
                    "generatedImagePath": summary["generatedImagePath"],
                    "publishPackagePath": summary["publishPackagePath"],
                },
            )
            if task_type == "scene_draft_to_image":
                try:
                    _reply_text_for_user(
                        project_dir=project_dir,
                        credentials=credentials,
                        user_openid=user_openid,
                        text_content=build_developer_continue_hint_text(),
                        source_message_id=source_message_id,
                        msg_seq=3 if source_message_id else 0,
                        event_id=reply_event_id,
                    )
                    _append_service_event(
                        project_dir,
                        {
                            "recordedAt": datetime.now().isoformat(timespec="seconds"),
                            "type": "developer_continue_hint_sent",
                            "runId": bundle.run_id,
                            "userOpenId": user_openid,
                        },
                    )
                except Exception as exc:
                    _append_service_event(
                        project_dir,
                        {
                            "recordedAt": datetime.now().isoformat(timespec="seconds"),
                            "type": "developer_continue_hint_failed",
                            "runId": bundle.run_id,
                            "userOpenId": user_openid,
                            "error": str(exc),
                        },
                    )
                    _emit_key_log(
                        log,
                        f"开发者模式完成提醒发送失败 runId={bundle.run_id} error={str(exc)[:120]}",
                    )
            _write_stage_status(
                project_dir=project_dir,
                status="idle",
                stage="completed",
                user_openid=user_openid,
                run_id=bundle.run_id,
                queued_count=task_queue.qsize(),
                generated_image_path=summary["generatedImagePath"],
                publish_package_path=summary["publishPackagePath"],
            )
            _emit_key_log(
                log,
                f"任务完成 runId={bundle.run_id} user={_mask_user_openid(user_openid)}",
            )
        except InterruptedError as exc:
            _append_service_event(
                project_dir,
                {
                    "recordedAt": datetime.now().isoformat(timespec="seconds"),
                    "type": "generation_interrupted",
                    "runId": bundle.run_id,
                    "userOpenId": user_openid,
                    "stage": str(service_runtime.get("currentStage", "")).strip(),
                    "reason": str(exc),
                },
            )
            _write_stage_status(
                project_dir=project_dir,
                status="idle",
                stage="interrupted",
                user_openid=user_openid,
                run_id=bundle.run_id,
                queued_count=task_queue.qsize(),
                error=str(exc),
            )
            _emit_key_log(
                log,
                f"任务已中断 runId={bundle.run_id} user={_mask_user_openid(user_openid)}",
            )
        except Exception as exc:
            try:
                if source_message_id:
                    _reply_text_for_user(
                        project_dir=project_dir,
                        credentials=credentials,
                        user_openid=user_openid,
                        text_content=build_failed_text_ui(exc),
                        source_message_id=source_message_id,
                        msg_seq=2,
                    )
                elif reply_event_id:
                    _reply_text_for_user(
                        project_dir=project_dir,
                        credentials=credentials,
                        user_openid=user_openid,
                        text_content=build_failed_text_ui(exc),
                        event_id=reply_event_id,
                    )
                else:
                    _reply_text_for_user(
                        project_dir=project_dir,
                        credentials=credentials,
                        user_openid=user_openid,
                        text_content=build_failed_text_ui(exc),
                    )
            except Exception:
                pass
            _append_service_event(
                project_dir,
                {
                    "recordedAt": datetime.now().isoformat(timespec="seconds"),
                    "type": "generation_failed",
                    "runId": bundle.run_id,
                    "userOpenId": user_openid,
                    "error": str(exc),
                    "runRoot": str(bundle.root),
                },
            )
            _write_stage_status(
                project_dir=project_dir,
                status="error",
                stage=str(service_runtime.get("currentStage", "")).strip() or "failed",
                user_openid=user_openid,
                run_id=bundle.run_id,
                queued_count=task_queue.qsize(),
                error=str(exc),
                failed_run_root=str(bundle.root),
            )
            _emit_key_log(
                log,
                f"任务失败 runId={bundle.run_id} user={_mask_user_openid(user_openid)} error={str(exc)[:120]}",
            )
        finally:
            with service_runtime_lock:
                service_runtime["activeRunId"] = None
                service_runtime["activeUserOpenId"] = ""
                service_runtime["activeSourceMessageId"] = ""
                service_runtime["currentStage"] = ""
                service_runtime["reserved"] = False
                service_runtime["interruptRequested"] = False
                service_runtime["interruptReason"] = ""
                service_runtime["busyNoticeUsers"] = set()
            task_queue.task_done()


def run_qq_bot_generate_service(
    project_dir: Path,
    *,
    config_path: Path,
    wait_seconds: int,
    ready_only: bool,
    trigger_command: str,
    help_command: str,
    status_command: str,
    reconnect_delay_seconds: float,
    log: Callable[[str], None] | None = None,
) -> None:
    lock_path = _acquire_service_lock(project_dir)
    clear_service_stop_request(project_dir)
    config = load_qq_bot_message_config(project_dir, config_path.resolve())
    credentials = resolve_qq_bot_credentials(
        project_dir,
        config,
        scene_override="user",
        target_openid_override="placeholder_user_openid",
    )
    stop_event = threading.Event()
    task_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)
    service_runtime = {
        "activeRunId": None,
        "activeUserOpenId": "",
        "activeSourceMessageId": "",
        "currentStage": "",
        "reserved": False,
        "interruptRequested": False,
        "interruptReason": "",
        "busyNoticeUsers": set(),
    }
    service_runtime_lock = threading.Lock()
    worker = threading.Thread(
        target=_task_worker,
        kwargs={
            "project_dir": project_dir,
            "credentials": credentials,
            "task_queue": task_queue,
            "stop_event": stop_event,
            "service_runtime": service_runtime,
            "service_runtime_lock": service_runtime_lock,
            "log": log,
        },
        daemon=True,
    )
    worker.start()

    started_at = time.time()
    handled_message_ids: set[str] = set()
    handled_message_order: deque[str] = deque()
    startup_guidance_sent = False

    _write_stage_status(
        project_dir=project_dir,
        status="starting",
        stage="initializing",
        queued_count=0,
    )

    interrupted = False
    shutdown_requested = False
    try:
        while True:
            if read_service_stop_request(project_dir):
                raise _ServiceShutdownRequested()
            deadline_reached = (not ready_only) and (wait_seconds > 0) and (time.time() - started_at >= wait_seconds)
            if deadline_reached:
                raise RuntimeError(f"Timed out after {wait_seconds} seconds waiting for trigger command.")

            ws = None
            connection_state = None
            try:
                token_response = fetch_app_access_token(
                    app_id=credentials["appId"],
                    app_secret=credentials["appSecret"],
                    access_token_url=credentials["accessTokenUrl"],
                    timeout_ms=credentials["timeoutMs"],
                )
                ws, connection_state = _connect_gateway(credentials, token_response)
                gateway_url = str(connection_state["gatewayInfo"]["url"])
                _write_stage_status(
                    project_dir=project_dir,
                    status="listening",
                    stage="waiting_for_trigger",
                    queued_count=task_queue.qsize(),
                )
                _emit_key_log(log, "网关已连接，正在后台监听 QQ 私聊。")
                if not ready_only and not startup_guidance_sent:
                    startup_guidance_sent = _send_startup_guidance_if_possible(
                        project_dir=project_dir,
                        credentials=credentials,
                        trigger_command=trigger_command,
                        help_command=help_command,
                        status_command=status_command,
                        log=log,
                    )

                while True:
                    if read_service_stop_request(project_dir):
                        raise _ServiceShutdownRequested()
                    if (not ready_only) and (wait_seconds > 0) and (time.time() - started_at >= wait_seconds):
                        raise RuntimeError(f"Timed out after {wait_seconds} seconds waiting for trigger command.")

                    raw_message, payload = _recv_gateway_payload(ws, timeout_seconds=DEFAULT_WS_RECV_TIMEOUT_SECONDS)
                    if raw_message is None or payload is None:
                        continue

                    if "s" in payload:
                        connection_state["state"]["seq"] = payload.get("s")

                    event_type = str(payload.get("t", "")).strip()
                    if event_type == "READY":
                        save_gateway_status(
                            project_dir,
                            gateway_url=gateway_url,
                            session_id=str(payload.get("d", {}).get("session_id", "")).strip(),
                            event_type=event_type,
                        )
                        if ready_only:
                            return
                        continue

                    if event_type != "C2C_MESSAGE_CREATE":
                        continue

                    source_message_id = str(payload.get("d", {}).get("id", "")).strip()
                    if source_message_id and source_message_id in handled_message_ids:
                        continue
                    _remember_handled_message(source_message_id, handled_message_ids, handled_message_order)

                    if payload.get("d", {}).get("author", {}).get("bot"):
                        continue

                    user_openid = extract_user_openid(payload)
                    if not user_openid:
                        continue

                    event_path = save_gateway_event(project_dir, payload=payload, raw_message=raw_message)
                    persist_user_openid(project_dir, user_openid=user_openid, event_path=event_path)

                    content = str(payload.get("d", {}).get("content", "")).strip()
                    user_state = load_private_user_state(project_dir, user_openid)
                    user_mode = normalize_private_mode(user_state.get("mode", MODE_EXPERIENCE))
                    pending_action = str(user_state.get("pendingAction", "")).strip()
                    interpretation = _interpret_private_message(
                        content=content,
                        user_mode=user_mode,
                        pending_action=pending_action,
                        status_text=_build_status_text(project_dir, mode=user_mode),
                        trigger_command=trigger_command,
                        help_command=help_command,
                        status_command=status_command,
                    )
                    interpretation_kind = str(interpretation.get("kind", "")).strip()
                    service_busy = _service_is_busy(service_runtime, service_runtime_lock)
                    _emit_key_log(
                        log,
                        f"收到私聊 user={_mask_user_openid(user_openid)} mode={user_mode} action={interpretation_kind}",
                    )
                    if service_busy and _is_non_interrupting_command(interpretation_kind):
                        _reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=str(interpretation["replyText"]),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    if service_busy and _is_interrupting_command(interpretation_kind):
                        next_mode = str(interpretation.get("nextMode", user_mode)).strip() or user_mode
                        next_pending_action = str(interpretation.get("nextPendingAction", pending_action)).strip()
                        if interpretation_kind == "switch_mode":
                            set_private_user_mode(project_dir, user_openid, next_mode)
                            set_private_user_pending_action(project_dir, user_openid, next_pending_action)
                            _replace_or_cancel_busy_task(
                                task_queue=task_queue,
                                service_runtime=service_runtime,
                                service_runtime_lock=service_runtime_lock,
                                replacement_task=None,
                                reason=f"switch_mode:{next_mode}",
                            )
                            _emit_key_log(
                                log,
                                f"生成中切换模式 user={_mask_user_openid(user_openid)} mode={next_mode}",
                            )
                            _reply_text_for_user(
                                project_dir=project_dir,
                                credentials=credentials,
                                user_openid=user_openid,
                                text_content=build_mode_switched_text(next_mode, task_running=True),
                                source_message_id=source_message_id,
                                msg_seq=1,
                            )
                            continue
                        if interpretation_kind == "developer_scene_prompt":
                            set_private_user_mode(project_dir, user_openid, MODE_DEVELOPER)
                            set_private_user_pending_action(project_dir, user_openid, PENDING_ACTION_SCENE_DRAFT)
                            _replace_or_cancel_busy_task(
                                task_queue=task_queue,
                                service_runtime=service_runtime,
                                service_runtime_lock=service_runtime_lock,
                                replacement_task=None,
                                reason="developer_scene_prompt",
                            )
                            _emit_key_log(
                                log,
                                f"生成中进入注入态 user={_mask_user_openid(user_openid)}",
                            )
                            _reply_text_for_user(
                                project_dir=project_dir,
                                credentials=credentials,
                                user_openid=user_openid,
                                text_content=build_developer_input_text(task_running=True),
                                source_message_id=source_message_id,
                                msg_seq=1,
                            )
                            continue
                        if interpretation_kind == "trigger_generation":
                            replacement_task = _build_full_generation_task(
                                user_openid=user_openid,
                                source_message_id=source_message_id,
                                event_id="",
                            )
                            _replace_or_cancel_busy_task(
                                task_queue=task_queue,
                                service_runtime=service_runtime,
                                service_runtime_lock=service_runtime_lock,
                                replacement_task=replacement_task,
                                reason="trigger_generation",
                            )
                            _emit_key_log(
                                log,
                                f"生成中收到新的生成命令 user={_mask_user_openid(user_openid)}",
                            )
                            _reply_text_for_user(
                                project_dir=project_dir,
                                credentials=credentials,
                                user_openid=user_openid,
                                text_content=build_started_text_ui(mode=normalize_private_mode(next_mode), interrupting=True),
                                source_message_id=source_message_id,
                                msg_seq=1,
                            )
                            continue
                    if service_busy:
                        if _should_reply_busy_once(
                            service_runtime,
                            service_runtime_lock,
                            user_openid=user_openid,
                        ):
                            reply_text = (
                                _build_scene_draft_busy_reply(project_dir)
                                if interpretation_kind in {"awaiting_scene_draft", "invalid_scene_draft", "scene_draft_submission"}
                                else _build_busy_text_for_mode(project_dir, mode=user_mode)
                            )
                            _reply_text_for_user(
                                project_dir=project_dir,
                                credentials=credentials,
                                user_openid=user_openid,
                                text_content=reply_text,
                                source_message_id=source_message_id,
                                msg_seq=1,
                            )
                        else:
                            _emit_key_log(
                                log,
                                f"忙碌期忽略普通消息 user={_mask_user_openid(user_openid)} mode={user_mode}",
                            )
                        continue
                    if interpretation_kind == "help":
                        _reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=str(interpretation["replyText"]),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    if interpretation_kind == "status":
                        _reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=str(interpretation["replyText"]),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    if interpretation_kind == "awaiting_scene_draft":
                        _reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=str(interpretation["replyText"]),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    if interpretation_kind == "same_mode_guidance":
                        _reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=str(interpretation["replyText"]),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    if interpretation_kind == "switch_mode":
                        next_mode = str(interpretation["nextMode"])
                        next_pending_action = str(interpretation.get("nextPendingAction", "")).strip()
                        set_private_user_mode(project_dir, user_openid, next_mode)
                        set_private_user_pending_action(project_dir, user_openid, next_pending_action)
                        _emit_key_log(
                            log,
                            f"已切换模式 user={_mask_user_openid(user_openid)} mode={next_mode}",
                        )
                        _reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=build_mode_switched_text(next_mode, task_running=service_busy),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    if interpretation_kind == "developer_scene_prompt":
                        set_private_user_mode(project_dir, user_openid, MODE_DEVELOPER)
                        set_private_user_pending_action(project_dir, user_openid, PENDING_ACTION_SCENE_DRAFT)
                        _emit_key_log(
                            log,
                            f"进入场景稿注入等待态 user={_mask_user_openid(user_openid)}",
                        )
                        _reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=build_developer_input_text(task_running=service_busy),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    if interpretation_kind == "invalid_scene_draft":
                        _reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=str(interpretation["replyText"]),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    if interpretation_kind == "scene_draft_submission":
                        scene_draft = dict(interpretation["sceneDraft"])
                        scene_draft_path = persist_scene_draft_message(
                            project_dir,
                            user_openid=user_openid,
                            scene_draft=scene_draft,
                        )
                        if not _accept_scene_draft_generation(
                            project_dir=project_dir,
                            task_queue=task_queue,
                            service_runtime=service_runtime,
                            service_runtime_lock=service_runtime_lock,
                            user_openid=user_openid,
                            scene_draft=scene_draft,
                            scene_draft_path=scene_draft_path,
                            source_message_id=source_message_id,
                        ):
                            _emit_key_log(
                                log,
                                f"拒绝新的场景稿任务 user={_mask_user_openid(user_openid)} reason=busy",
                            )
                            _reply_busy(
                                project_dir=project_dir,
                                credentials=credentials,
                                user_openid=user_openid,
                                mode=MODE_DEVELOPER,
                                source_message_id=source_message_id,
                                msg_seq=1,
                            )
                            continue
                        set_private_user_pending_action(project_dir, user_openid, PENDING_ACTION_SCENE_DRAFT)
                        _emit_key_log(
                            log,
                            f"已接收场景稿任务 user={_mask_user_openid(user_openid)} path={scene_draft_path.name}",
                        )
                        _reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=str(interpretation["replyText"]),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    if interpretation_kind == "wrong_mode_command":
                        _reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=str(interpretation["replyText"]),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    if interpretation_kind == "unknown":
                        _reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=str(interpretation["replyText"]),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue

                    if not _accept_full_generation(
                        project_dir=project_dir,
                        task_queue=task_queue,
                        service_runtime=service_runtime,
                        service_runtime_lock=service_runtime_lock,
                        user_openid=user_openid,
                        source_message_id=source_message_id,
                    ):
                        _emit_key_log(
                            log,
                            f"拒绝新的生成请求 user={_mask_user_openid(user_openid)} reason=busy",
                        )
                        _reply_busy(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            mode=normalize_private_mode(str(interpretation.get("nextMode", user_mode))),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    _emit_key_log(
                        log,
                        f"已接收生成请求 user={_mask_user_openid(user_openid)}",
                    )
                    _reply_text_for_user(
                        project_dir=project_dir,
                        credentials=credentials,
                        user_openid=user_openid,
                        text_content=str(interpretation["replyText"]),
                        source_message_id=source_message_id,
                        msg_seq=1,
                    )
            except _ServiceShutdownRequested:
                shutdown_requested = True
                stop_event.set()
                stop_payload = read_service_stop_request(project_dir) or {}
                _mark_shutdown_requested(
                    project_dir=project_dir,
                    service_runtime=service_runtime,
                    service_runtime_lock=service_runtime_lock,
                    task_queue=task_queue,
                    reason=str(stop_payload.get("reason", "")).strip() or "shutdown requested",
                )
                while True:
                    runtime_snapshot = _snapshot_service_runtime(service_runtime, service_runtime_lock)
                    has_active_run = bool(runtime_snapshot.get("activeRunId")) or bool(runtime_snapshot.get("reserved"))
                    has_queued_task = task_queue.qsize() > 0
                    if not has_active_run and not has_queued_task:
                        break
                    time.sleep(0.5)
                break
            except (RuntimeError, WebSocketConnectionClosedException, OSError) as exc:
                if ready_only:
                    raise RuntimeError(str(exc)) from exc
                _write_stage_status(
                    project_dir=project_dir,
                    status="reconnecting",
                    stage="gateway_reconnecting",
                    queued_count=task_queue.qsize(),
                    error=str(exc),
                )
                if log is not None:
                    log(f"[qq-generate] 连接异常，{reconnect_delay_seconds:.1f} 秒后重连: {exc}")
                time.sleep(max(reconnect_delay_seconds, 1.0))
                continue
            finally:
                if connection_state is not None:
                    connection_state["state"]["running"] = False
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass
    except KeyboardInterrupt:
        interrupted = True
        runtime_snapshot = _snapshot_service_runtime(service_runtime, service_runtime_lock)
        _append_service_event(
            project_dir,
            {
                "recordedAt": datetime.now().isoformat(timespec="seconds"),
                "type": "service_interrupt_requested",
                "runId": str(runtime_snapshot.get("activeRunId") or "").strip(),
                "stage": str(runtime_snapshot.get("currentStage") or "").strip(),
            },
        )
        _write_stage_status(
            project_dir=project_dir,
            status="stopping",
            stage=str(runtime_snapshot.get("currentStage") or "").strip() or "shutdown_requested",
            user_openid=str(runtime_snapshot.get("activeUserOpenId") or "").strip(),
            source_message_id=str(runtime_snapshot.get("activeSourceMessageId") or "").strip(),
            run_id=str(runtime_snapshot.get("activeRunId") or "").strip(),
            queued_count=task_queue.qsize(),
        )
    finally:
        stop_event.set()
        try:
            worker.join(timeout=1.5)
        except Exception:
            pass
        runtime_snapshot = _snapshot_service_runtime(service_runtime, service_runtime_lock)
        _append_service_event(
            project_dir,
            {
                "recordedAt": datetime.now().isoformat(timespec="seconds"),
                "type": "service_stopped",
                "runId": str(runtime_snapshot.get("activeRunId") or "").strip(),
                "stage": str(runtime_snapshot.get("currentStage") or "").strip(),
                "interrupted": interrupted,
                "shutdownRequested": shutdown_requested,
            },
        )
        _write_stage_status(
            project_dir=project_dir,
            status="stopped",
            stage="shutdown_complete"
            if (interrupted or shutdown_requested)
            else str(runtime_snapshot.get("currentStage") or "").strip() or "stopped",
            user_openid=str(runtime_snapshot.get("activeUserOpenId") or "").strip(),
            source_message_id=str(runtime_snapshot.get("activeSourceMessageId") or "").strip(),
            run_id=str(runtime_snapshot.get("activeRunId") or "").strip(),
            queued_count=task_queue.qsize(),
        )
        clear_service_stop_request(project_dir)
        _release_service_lock(lock_path)
