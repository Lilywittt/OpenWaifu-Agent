from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from generation_slot import read_generation_slot

from .qq_bot_job_queue import QQBotJobQueue
from .qq_bot_private_state import load_private_user_state
from .qq_bot_private_ui import (
    MODE_DEVELOPER,
    MODE_EXPERIENCE,
    build_busy_text as build_busy_text_ui,
    build_developer_input_received_text,
    build_enqueued_text,
    build_existing_task_text,
    build_failed_text as build_failed_text_ui,
    build_scene_draft_busy_text,
    build_started_text as build_started_text_ui,
    build_status_text_from_payload,
    normalize_private_mode,
)
from .qq_bot_runtime_store import read_service_status, snapshot_service_runtime, write_stage_status


def user_mode(project_dir: Path, user_openid: str) -> str:
    payload = load_private_user_state(project_dir, user_openid)
    return normalize_private_mode(str(payload.get("mode", MODE_EXPERIENCE)))


def load_status_payload(project_dir: Path) -> dict[str, Any] | None:
    return read_service_status(project_dir)


def build_help_text(trigger_command: str, help_command: str, *, mode: str = MODE_EXPERIENCE) -> str:
    from .qq_bot_private_ui import build_help_text as build_help_text_ui
    from .qq_bot_router import DEFAULT_STATUS_COMMAND

    return build_help_text_ui(trigger_command, help_command, DEFAULT_STATUS_COMMAND, mode=mode)


def build_busy_text(project_dir: Path) -> str:
    return build_busy_text_ui(build_status_text(project_dir))


def build_busy_text_for_mode(
    project_dir: Path,
    *,
    mode: str,
    user_openid: str = "",
    job_queue: QQBotJobQueue | None = None,
) -> str:
    if job_queue is not None and user_openid:
        status_text = build_status_text(project_dir, mode=mode, user_openid=user_openid, job_queue=job_queue)
    else:
        status_payload = load_status_payload(project_dir)
        status_text = build_status_text_from_payload(status_payload, mode=mode) if status_payload else ""
    return build_busy_text_ui(status_text, mode=mode)


def build_scene_draft_busy_reply(
    project_dir: Path,
    *,
    user_openid: str = "",
    job_queue: QQBotJobQueue | None = None,
) -> str:
    if job_queue is not None and user_openid:
        status_text = build_status_text(project_dir, mode=MODE_DEVELOPER, user_openid=user_openid, job_queue=job_queue)
    else:
        status_payload = load_status_payload(project_dir)
        status_text = build_status_text_from_payload(status_payload, mode=MODE_DEVELOPER) if status_payload else ""
    return build_scene_draft_busy_text(status_text)


def build_started_text(*, mode: str = MODE_EXPERIENCE) -> str:
    return build_started_text_ui(mode=mode)


def build_failed_text(exc: Exception) -> str:
    return build_failed_text_ui(exc)


def build_enqueued_reply_text(result: dict[str, Any], *, mode: str, base_text: str = "") -> str:
    queue_position = int(result.get("queuePosition", 0) or 0)
    queue_size = int(result.get("queueSize", 0) or 0)
    queued_text = build_enqueued_text(queue_position, queue_size, mode=mode)
    if base_text:
        return "\n".join([str(base_text).strip(), "", queued_text])
    return queued_text


def build_existing_task_reply_text(
    project_dir: Path,
    *,
    mode: str,
    user_openid: str,
    job_queue: QQBotJobQueue,
) -> str:
    return build_existing_task_text(
        build_status_text(project_dir, mode=mode, user_openid=user_openid, job_queue=job_queue),
        mode=mode,
    )


def write_queue_accept_status(
    project_dir: Path,
    *,
    job_queue: QQBotJobQueue,
    service_runtime: dict[str, Any],
    service_runtime_lock: threading.Lock,
    queued_stage: str,
    user_openid: str,
    source_message_id: str,
    queue_position: int,
    queue_size: int,
) -> None:
    runtime_snapshot = snapshot_service_runtime(service_runtime, service_runtime_lock)
    queued_count = job_queue.pending_count()
    active_run_id = str(runtime_snapshot.get("activeRunId") or "").strip()
    if active_run_id:
        write_stage_status(
            project_dir=project_dir,
            status="running",
            stage=str(runtime_snapshot.get("currentStage") or "").strip() or "starting",
            user_openid=str(runtime_snapshot.get("activeUserOpenId") or "").strip(),
            source_message_id=str(runtime_snapshot.get("activeSourceMessageId") or "").strip(),
            run_id=active_run_id,
            queued_count=queued_count,
        )
        return
    write_stage_status(
        project_dir=project_dir,
        status="queued",
        stage=queued_stage,
        user_openid=user_openid,
        source_message_id=source_message_id,
        queued_count=queued_count,
        queue_position=queue_position,
        queue_size=queue_size,
    )


def build_status_text(
    project_dir: Path,
    *,
    mode: str = MODE_EXPERIENCE,
    user_openid: str = "",
    job_queue: QQBotJobQueue | None = None,
) -> str:
    payload = load_status_payload(project_dir)
    if payload is None:
        payload = {"status": "idle", "stage": "waiting_for_trigger", "queuedCount": 0}
    if job_queue is not None and user_openid:
        payload = dict(payload)
        queue_info = job_queue.get_user_queue_info(user_openid)
        active_user_openid = str(payload.get("userOpenId", "")).strip()
        if queue_info:
            payload["queuePosition"] = queue_info.get("queuePosition", 0)
            payload["queueSize"] = queue_info.get("queueSize", 0)
            payload["queuedCount"] = queue_info.get("queueSize", 0)
            if active_user_openid and active_user_openid != user_openid:
                payload["status"] = "queued"
                payload["stage"] = "waiting_in_queue"
            elif not str(payload.get("status", "")).strip():
                payload["status"] = "queued"
        elif str(payload.get("status", "")).strip() == "running" and active_user_openid and active_user_openid != user_openid:
            payload["status"] = "busy_other"
            payload["queuedCount"] = job_queue.pending_count()
    return build_status_text_from_payload(payload, mode=mode)


def service_is_busy(
    service_runtime: dict[str, Any],
    service_runtime_lock: threading.Lock,
    job_queue: QQBotJobQueue | None = None,
) -> bool:
    snapshot = snapshot_service_runtime(service_runtime, service_runtime_lock)
    if snapshot.get("activeRunId") or snapshot.get("reserved"):
        return True
    if job_queue is not None and job_queue.pending_count() > 0:
        return True
    return False


def should_reply_busy_once(
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


def clear_busy_reply_tracking(service_runtime: dict[str, Any], service_runtime_lock: threading.Lock) -> None:
    with service_runtime_lock:
        service_runtime["busyNoticeUsers"] = set()


def is_interrupt_requested(service_runtime: dict[str, Any], service_runtime_lock: threading.Lock) -> bool:
    with service_runtime_lock:
        return bool(service_runtime.get("interruptRequested"))


def current_status_payload(project_dir: Path, job_queue: QQBotJobQueue) -> dict[str, Any]:
    return load_status_payload(project_dir) or {
        "status": "idle",
        "stage": "waiting_for_trigger",
        "queuedCount": job_queue.pending_count(),
    }


def enqueue_generation_task(
    *,
    project_dir: Path,
    job_queue: QQBotJobQueue,
    service_runtime: dict[str, Any],
    service_runtime_lock: threading.Lock,
    user_openid: str,
    source_message_id: str = "",
    reply_event_id: str = "",
    task_type: str = "full_generation",
    scene_draft: dict[str, Any] | None = None,
    scene_draft_path: Path | None = None,
) -> dict[str, Any]:
    slot_holder = read_generation_slot(project_dir, cleanup_stale=True)
    if slot_holder is not None:
        return {
            "accepted": False,
            "reason": "slot_busy",
            "holder": slot_holder,
        }
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
    with service_runtime_lock:
        service_runtime["reserved"] = True
    result = job_queue.enqueue(
        user_openid=user_openid,
        job_kind=task_type,
        payload=task,
        mode=user_mode(project_dir, user_openid),
        source_message_id=source_message_id,
    )
    with service_runtime_lock:
        service_runtime["reserved"] = False
    return result


def accept_full_generation(
    *,
    project_dir: Path,
    job_queue: QQBotJobQueue,
    service_runtime: dict[str, Any],
    service_runtime_lock: threading.Lock,
    user_openid: str,
    source_message_id: str = "",
    event_id: str = "",
) -> dict[str, Any]:
    result = enqueue_generation_task(
        project_dir=project_dir,
        job_queue=job_queue,
        service_runtime=service_runtime,
        service_runtime_lock=service_runtime_lock,
        user_openid=user_openid,
        source_message_id=source_message_id,
        reply_event_id=event_id,
        task_type="full_generation",
    )
    if result.get("accepted"):
        write_queue_accept_status(
            project_dir,
            job_queue=job_queue,
            service_runtime=service_runtime,
            service_runtime_lock=service_runtime_lock,
            queued_stage="queued_for_generation",
            user_openid=user_openid,
            source_message_id=source_message_id,
            queue_position=int(result.get("queuePosition", 0) or 0),
            queue_size=int(result.get("queueSize", 0) or 0),
        )
    return result


def accept_scene_draft_generation(
    *,
    project_dir: Path,
    job_queue: QQBotJobQueue,
    service_runtime: dict[str, Any],
    service_runtime_lock: threading.Lock,
    user_openid: str,
    scene_draft: dict[str, Any],
    scene_draft_path: Path,
    source_message_id: str = "",
    event_id: str = "",
) -> dict[str, Any]:
    result = enqueue_generation_task(
        project_dir=project_dir,
        job_queue=job_queue,
        service_runtime=service_runtime,
        service_runtime_lock=service_runtime_lock,
        user_openid=user_openid,
        source_message_id=source_message_id,
        reply_event_id=event_id,
        task_type="scene_draft_to_image",
        scene_draft=scene_draft,
        scene_draft_path=scene_draft_path,
    )
    if result.get("accepted"):
        write_queue_accept_status(
            project_dir,
            job_queue=job_queue,
            service_runtime=service_runtime,
            service_runtime_lock=service_runtime_lock,
            queued_stage="queued_for_scene_draft_generation",
            user_openid=user_openid,
            source_message_id=source_message_id,
            queue_position=int(result.get("queuePosition", 0) or 0),
            queue_size=int(result.get("queueSize", 0) or 0),
        )
    return result
