from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from websocket._exceptions import WebSocketConnectionClosedException

from generation_slot import read_generation_slot
from runtime_layout import update_latest

from .qq_bot_client import load_qq_bot_message_config, resolve_qq_bot_credentials
from .qq_bot_executor import (
    create_generation_bundle,
    reply_text_for_user,
    run_generation_task,
    send_startup_guidance_if_possible,
)
from .qq_bot_gateway import persist_user_openid, save_gateway_event, save_gateway_status
from .qq_bot_identity import extract_user_openid
from .qq_bot_ingress import connect_gateway, fetch_access_token, recv_gateway_payload
from .qq_bot_job_queue import QQBotJobQueue
from .qq_bot_private_state import (
    PENDING_ACTION_SCENE_DRAFT,
    load_private_user_state,
    set_private_user_mode,
    set_private_user_pending_action,
)
from .qq_bot_private_ui import (
    MODE_DEVELOPER,
    MODE_EXPERIENCE,
    build_developer_continue_hint_text,
    build_developer_input_received_text,
    build_developer_input_text,
    build_external_slot_busy_text,
    build_mode_switched_text,
    normalize_private_mode,
    build_queue_full_text,
)
from .qq_bot_router import (
    DEFAULT_HELP_COMMAND,
    DEFAULT_STATUS_COMMAND,
    DEFAULT_TRIGGER_COMMAND,
    interpret_private_message,
)
from .qq_bot_runtime_store import (
    ServiceShutdownRequested,
    acquire_service_lock,
    append_service_event,
    clear_service_stop_request,
    mark_shutdown_requested,
    read_service_stop_request,
    release_service_lock,
    snapshot_service_runtime,
    write_stage_status,
)
from .qq_bot_scene_draft import persist_scene_draft_message
from .qq_bot_service_support import emit_key_log, mask_user_openid, remember_handled_message
from .qq_bot_task_policy import (
    accept_full_generation,
    accept_scene_draft_generation,
    build_busy_text_for_mode,
    build_enqueued_reply_text,
    build_existing_task_reply_text,
    build_failed_text,
    build_scene_draft_busy_reply,
    build_status_text,
    service_is_busy,
    should_reply_busy_once,
    user_mode,
)


DEFAULT_WS_RECV_TIMEOUT_SECONDS = 2.0
DEFAULT_RECONNECT_DELAY_SECONDS = 3.0


def task_worker(
    *,
    project_dir: Path,
    credentials: dict,
    job_queue: QQBotJobQueue,
    stop_event: threading.Event,
    service_runtime: dict[str, Any],
    service_runtime_lock: threading.Lock,
    log: Callable[[str], None] | None,
) -> None:
    while not stop_event.is_set():
        slot_holder = read_generation_slot(project_dir, cleanup_stale=True)
        if slot_holder is not None and str(slot_holder.get("ownerType", "")).strip() != "qq_bot_service":
            time.sleep(1.0)
            continue
        task = job_queue.fetch_next_pending()
        if task is None:
            time.sleep(1.0)
            continue

        job_id = int(task["jobId"])
        user_openid = str(task["userOpenId"]).strip()
        payload = dict(task.get("payload", {}) or {})
        source_message_id = str(payload.get("sourceMessageId", "")).strip()
        reply_event_id = str(payload.get("replyEventId", "")).strip()
        task_type = str(task.get("jobKind", payload.get("taskType", "full_generation"))).strip()
        bundle = create_generation_bundle(project_dir, task_type=task_type, user_openid=user_openid)
        emit_key_log(log, f"开始执行任务 runId={bundle.run_id} type={task_type} user={mask_user_openid(user_openid)}")

        with service_runtime_lock:
            service_runtime["activeRunId"] = bundle.run_id
            service_runtime["activeUserOpenId"] = user_openid
            service_runtime["activeSourceMessageId"] = source_message_id
            service_runtime["currentStage"] = "starting"
            service_runtime["interruptRequested"] = False
            service_runtime["interruptReason"] = ""
            service_runtime["busyNoticeUsers"] = set()

        write_stage_status(
            project_dir=project_dir,
            status="running",
            stage="starting",
            user_openid=user_openid,
            source_message_id=source_message_id,
            run_id=bundle.run_id,
            queued_count=job_queue.pending_count(),
        )

        def _task_log(message: str) -> None:
            with service_runtime_lock:
                service_runtime["currentStage"] = message
                interrupt_requested = bool(service_runtime.get("interruptRequested"))
            append_service_event(
                project_dir,
                {
                    "recordedAt": datetime.now().isoformat(timespec="seconds"),
                    "type": "generation_log",
                    "runId": bundle.run_id,
                    "message": message,
                },
            )
            write_stage_status(
                project_dir=project_dir,
                status="running",
                stage=message,
                user_openid=user_openid,
                source_message_id=source_message_id,
                run_id=bundle.run_id,
                queued_count=job_queue.pending_count(),
            )
            if log is not None:
                log(message)
            if interrupt_requested:
                raise InterruptedError("Generation interrupted by command.")

        def _should_abort_task() -> bool:
            with service_runtime_lock:
                return bool(service_runtime.get("interruptRequested"))

        try:
            task_payload = dict(payload)
            task_payload["userOpenId"] = user_openid
            task_payload["taskType"] = task_type
            result = run_generation_task(
                project_dir=project_dir,
                bundle=bundle,
                task=task_payload,
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
            append_service_event(
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
                    reply_text_for_user(
                        project_dir=project_dir,
                        credentials=credentials,
                        user_openid=user_openid,
                        text_content=build_developer_continue_hint_text(),
                        source_message_id=source_message_id,
                        msg_seq=3 if source_message_id else 0,
                        event_id=reply_event_id,
                    )
                    append_service_event(
                        project_dir,
                        {
                            "recordedAt": datetime.now().isoformat(timespec="seconds"),
                            "type": "developer_continue_hint_sent",
                            "runId": bundle.run_id,
                            "userOpenId": user_openid,
                        },
                    )
                except Exception as exc:
                    append_service_event(
                        project_dir,
                        {
                            "recordedAt": datetime.now().isoformat(timespec="seconds"),
                            "type": "developer_continue_hint_failed",
                            "runId": bundle.run_id,
                            "userOpenId": user_openid,
                            "error": str(exc),
                        },
                    )
                    emit_key_log(log, f"开发者模式完成提醒发送失败 runId={bundle.run_id} error={str(exc)[:120]}")
            write_stage_status(
                project_dir=project_dir,
                status="idle",
                stage="completed",
                user_openid=user_openid,
                run_id=bundle.run_id,
                queued_count=job_queue.pending_count(),
                generated_image_path=summary["generatedImagePath"],
                publish_package_path=summary["publishPackagePath"],
            )
            job_queue.mark_completed(job_id, run_id=bundle.run_id)
            emit_key_log(log, f"任务完成 runId={bundle.run_id} user={mask_user_openid(user_openid)}")
        except InterruptedError as exc:
            append_service_event(
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
            write_stage_status(
                project_dir=project_dir,
                status="idle",
                stage="interrupted",
                user_openid=user_openid,
                run_id=bundle.run_id,
                queued_count=job_queue.pending_count(),
                error=str(exc),
            )
            job_queue.mark_canceled(job_id, reason=str(exc))
            emit_key_log(log, f"任务已中断 runId={bundle.run_id} user={mask_user_openid(user_openid)}")
        except Exception as exc:
            try:
                reply_kwargs = {
                    "project_dir": project_dir,
                    "credentials": credentials,
                    "user_openid": user_openid,
                    "text_content": build_failed_text(exc),
                }
                if source_message_id:
                    reply_kwargs["source_message_id"] = source_message_id
                    reply_kwargs["msg_seq"] = 2
                elif reply_event_id:
                    reply_kwargs["event_id"] = reply_event_id
                reply_text_for_user(**reply_kwargs)
            except Exception:
                pass
            append_service_event(
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
            write_stage_status(
                project_dir=project_dir,
                status="error",
                stage=str(service_runtime.get("currentStage", "")).strip() or "failed",
                user_openid=user_openid,
                run_id=bundle.run_id,
                queued_count=job_queue.pending_count(),
                error=str(exc),
                failed_run_root=str(bundle.root),
            )
            job_queue.mark_failed(job_id, error=str(exc), run_id=bundle.run_id)
            emit_key_log(log, f"任务失败 runId={bundle.run_id} user={mask_user_openid(user_openid)} error={str(exc)[:120]}")
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


def run_qq_bot_generate_service(
    project_dir: Path,
    *,
    config_path: Path,
    wait_seconds: int,
    ready_only: bool,
    trigger_command: str = DEFAULT_TRIGGER_COMMAND,
    help_command: str = DEFAULT_HELP_COMMAND,
    status_command: str = DEFAULT_STATUS_COMMAND,
    reconnect_delay_seconds: float = DEFAULT_RECONNECT_DELAY_SECONDS,
    log: Callable[[str], None] | None = None,
) -> None:
    lock_path = acquire_service_lock(project_dir)
    clear_service_stop_request(project_dir)
    config = load_qq_bot_message_config(project_dir, config_path.resolve())
    credentials = resolve_qq_bot_credentials(
        project_dir,
        config,
        scene_override="user",
        target_openid_override="placeholder_user_openid",
    )
    stop_event = threading.Event()
    job_queue = QQBotJobQueue(project_dir)
    recovered_jobs = job_queue.reset_abandoned_running()
    if recovered_jobs:
        emit_key_log(log, f"检测到 {recovered_jobs} 条中断任务，已回退到排队状态。")
    normalized_jobs = job_queue.enforce_single_inflight(reason="normalized on service startup")
    if normalized_jobs:
        emit_key_log(log, f"检测到 {normalized_jobs} 条历史重复任务，已按单用户单任务规则收敛。")
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
        target=task_worker,
        kwargs={
            "project_dir": project_dir,
            "credentials": credentials,
            "job_queue": job_queue,
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

    write_stage_status(
        project_dir=project_dir,
        status="starting",
        stage="initializing",
        queued_count=job_queue.pending_count(),
    )

    interrupted = False
    shutdown_requested = False
    try:
        while True:
            if read_service_stop_request(project_dir):
                raise ServiceShutdownRequested()
            deadline_reached = (not ready_only) and (wait_seconds > 0) and (time.time() - started_at >= wait_seconds)
            if deadline_reached:
                raise RuntimeError(f"Timed out after {wait_seconds} seconds waiting for trigger command.")

            ws = None
            connection_state = None
            try:
                token_response = fetch_access_token(credentials)
                ws, connection_state = connect_gateway(credentials, token_response)
                gateway_url = str(connection_state["gatewayInfo"]["url"])
                write_stage_status(
                    project_dir=project_dir,
                    status="listening",
                    stage="waiting_for_trigger",
                    queued_count=job_queue.pending_count(),
                )
                emit_key_log(log, "网关已连接，正在后台监听 QQ 私聊。")
                if not ready_only and not startup_guidance_sent:
                    startup_guidance_sent = send_startup_guidance_if_possible(
                        project_dir=project_dir,
                        credentials=credentials,
                        trigger_command=trigger_command,
                        help_command=help_command,
                        status_command=status_command,
                        user_mode_loader=user_mode,
                        log=log,
                    )

                while True:
                    if read_service_stop_request(project_dir):
                        raise ServiceShutdownRequested()
                    if (not ready_only) and (wait_seconds > 0) and (time.time() - started_at >= wait_seconds):
                        raise RuntimeError(f"Timed out after {wait_seconds} seconds waiting for trigger command.")

                    raw_message, payload = recv_gateway_payload(ws, timeout_seconds=DEFAULT_WS_RECV_TIMEOUT_SECONDS)
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
                    remember_handled_message(source_message_id, handled_message_ids, handled_message_order)

                    if payload.get("d", {}).get("author", {}).get("bot"):
                        continue

                    user_openid = extract_user_openid(payload)
                    if not user_openid:
                        continue

                    event_path = save_gateway_event(project_dir, payload=payload, raw_message=raw_message)
                    persist_user_openid(project_dir, user_openid=user_openid, event_path=event_path)

                    content = str(payload.get("d", {}).get("content", "")).strip()
                    user_state = load_private_user_state(project_dir, user_openid)
                    current_mode = normalize_private_mode(user_state.get("mode", MODE_EXPERIENCE))
                    pending_action = str(user_state.get("pendingAction", "")).strip()
                    interpretation = interpret_private_message(
                        content=content,
                        user_mode=current_mode,
                        pending_action=pending_action,
                        status_text=build_status_text(
                            project_dir,
                            mode=current_mode,
                            user_openid=user_openid,
                            job_queue=job_queue,
                        ),
                        trigger_command=trigger_command,
                        help_command=help_command,
                        status_command=status_command,
                    )
                    interpretation_kind = str(interpretation.get("kind", "")).strip()
                    service_busy = service_is_busy(service_runtime, service_runtime_lock, job_queue=job_queue)
                    emit_key_log(log, f"收到私聊 user={mask_user_openid(user_openid)} mode={current_mode} action={interpretation_kind}")

                    if service_busy:
                        if interpretation_kind in {"help", "status", "wrong_mode_command", "same_mode_guidance"}:
                            reply_text_for_user(
                                project_dir=project_dir,
                                credentials=credentials,
                                user_openid=user_openid,
                                text_content=str(interpretation["replyText"]),
                                source_message_id=source_message_id,
                                msg_seq=1,
                            )
                            continue
                        if interpretation_kind == "switch_mode":
                            next_mode = str(interpretation.get("nextMode", current_mode)).strip() or current_mode
                            next_pending_action = str(interpretation.get("nextPendingAction", pending_action)).strip()
                            set_private_user_mode(project_dir, user_openid, next_mode)
                            set_private_user_pending_action(project_dir, user_openid, next_pending_action)
                            emit_key_log(log, f"忙碌期切换模式 user={mask_user_openid(user_openid)} mode={next_mode}")
                            reply_text_for_user(
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
                            emit_key_log(log, f"忙碌期进入注入态 user={mask_user_openid(user_openid)}")
                            reply_text_for_user(
                                project_dir=project_dir,
                                credentials=credentials,
                                user_openid=user_openid,
                                text_content=build_developer_input_text(task_running=True),
                                source_message_id=source_message_id,
                                msg_seq=1,
                            )
                            continue
                        if interpretation_kind == "trigger_generation":
                            result = accept_full_generation(
                                project_dir=project_dir,
                                job_queue=job_queue,
                                service_runtime=service_runtime,
                                service_runtime_lock=service_runtime_lock,
                                user_openid=user_openid,
                                source_message_id=source_message_id,
                            )
                            if not result.get("accepted"):
                                if str(result.get("reason", "")).strip() == "user_inflight":
                                    emit_key_log(log, f"拒绝重复生成请求 user={mask_user_openid(user_openid)} reason=user_inflight")
                                    reply_text_for_user(
                                        project_dir=project_dir,
                                        credentials=credentials,
                                        user_openid=user_openid,
                                        text_content=build_existing_task_reply_text(
                                            project_dir,
                                            mode=normalize_private_mode(current_mode),
                                            user_openid=user_openid,
                                            job_queue=job_queue,
                                        ),
                                        source_message_id=source_message_id,
                                        msg_seq=1,
                                    )
                                    continue
                                if str(result.get("reason", "")).strip() == "slot_busy":
                                    emit_key_log(log, f"拒绝新的生成请求 user={mask_user_openid(user_openid)} reason=slot_busy")
                                    reply_text_for_user(
                                        project_dir=project_dir,
                                        credentials=credentials,
                                        user_openid=user_openid,
                                        text_content=build_external_slot_busy_text(
                                            str((result.get("holder") or {}).get("busyMessage", "")).strip(),
                                            mode=normalize_private_mode(current_mode),
                                        ),
                                        source_message_id=source_message_id,
                                        msg_seq=1,
                                    )
                                    continue
                                reply_text_for_user(
                                    project_dir=project_dir,
                                    credentials=credentials,
                                    user_openid=user_openid,
                                    text_content=build_queue_full_text(int(result.get("queueSize", 0) or 0)),
                                    source_message_id=source_message_id,
                                    msg_seq=1,
                                )
                                continue
                            busy_text = build_busy_text_for_mode(
                                project_dir,
                                mode=current_mode,
                                user_openid=user_openid,
                                job_queue=job_queue,
                            )
                            emit_key_log(log, f"忙碌期排队生成 user={mask_user_openid(user_openid)}")
                            reply_text_for_user(
                                project_dir=project_dir,
                                credentials=credentials,
                                user_openid=user_openid,
                                text_content=build_enqueued_reply_text(
                                    result,
                                    mode=normalize_private_mode(current_mode),
                                    base_text=busy_text,
                                ),
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
                            result = accept_scene_draft_generation(
                                project_dir=project_dir,
                                job_queue=job_queue,
                                service_runtime=service_runtime,
                                service_runtime_lock=service_runtime_lock,
                                user_openid=user_openid,
                                scene_draft=scene_draft,
                                scene_draft_path=scene_draft_path,
                                source_message_id=source_message_id,
                            )
                            if not result.get("accepted"):
                                if str(result.get("reason", "")).strip() == "user_inflight":
                                    emit_key_log(log, f"拒绝重复场景稿任务 user={mask_user_openid(user_openid)} reason=user_inflight")
                                    reply_text_for_user(
                                        project_dir=project_dir,
                                        credentials=credentials,
                                        user_openid=user_openid,
                                        text_content=build_existing_task_reply_text(
                                            project_dir,
                                            mode=MODE_DEVELOPER,
                                            user_openid=user_openid,
                                            job_queue=job_queue,
                                        ),
                                        source_message_id=source_message_id,
                                        msg_seq=1,
                                    )
                                    continue
                                if str(result.get("reason", "")).strip() == "slot_busy":
                                    emit_key_log(log, f"拒绝新的场景稿任务 user={mask_user_openid(user_openid)} reason=slot_busy")
                                    reply_text_for_user(
                                        project_dir=project_dir,
                                        credentials=credentials,
                                        user_openid=user_openid,
                                        text_content=build_external_slot_busy_text(
                                            str((result.get("holder") or {}).get("busyMessage", "")).strip(),
                                            mode=MODE_DEVELOPER,
                                        ),
                                        source_message_id=source_message_id,
                                        msg_seq=1,
                                    )
                                    continue
                                reply_text_for_user(
                                    project_dir=project_dir,
                                    credentials=credentials,
                                    user_openid=user_openid,
                                    text_content=build_queue_full_text(int(result.get("queueSize", 0) or 0)),
                                    source_message_id=source_message_id,
                                    msg_seq=1,
                                )
                                continue
                            set_private_user_pending_action(project_dir, user_openid, PENDING_ACTION_SCENE_DRAFT)
                            emit_key_log(log, f"忙碌期排队场景稿 user={mask_user_openid(user_openid)} path={scene_draft_path.name}")
                            reply_text_for_user(
                                project_dir=project_dir,
                                credentials=credentials,
                                user_openid=user_openid,
                                text_content=build_enqueued_reply_text(
                                    result,
                                    mode=MODE_DEVELOPER,
                                    base_text=build_developer_input_received_text(
                                        scene_draft.get("scenePremiseZh", ""),
                                        queued=True,
                                    ),
                                ),
                                source_message_id=source_message_id,
                                msg_seq=1,
                            )
                            continue
                        if should_reply_busy_once(service_runtime, service_runtime_lock, user_openid=user_openid):
                            reply_text = (
                                build_scene_draft_busy_reply(
                                    project_dir,
                                    user_openid=user_openid,
                                    job_queue=job_queue,
                                )
                                if interpretation_kind in {"awaiting_scene_draft", "invalid_scene_draft"}
                                else build_busy_text_for_mode(
                                    project_dir,
                                    mode=current_mode,
                                    user_openid=user_openid,
                                    job_queue=job_queue,
                                )
                            )
                            reply_text_for_user(
                                project_dir=project_dir,
                                credentials=credentials,
                                user_openid=user_openid,
                                text_content=reply_text,
                                source_message_id=source_message_id,
                                msg_seq=1,
                            )
                        else:
                            emit_key_log(log, f"忙碌期忽略普通消息 user={mask_user_openid(user_openid)} mode={current_mode}")
                        continue

                    if interpretation_kind == "help":
                        reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=str(interpretation["replyText"]),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    if interpretation_kind == "status":
                        reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=str(interpretation["replyText"]),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    if interpretation_kind == "awaiting_scene_draft":
                        reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=str(interpretation["replyText"]),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    if interpretation_kind == "same_mode_guidance":
                        reply_text_for_user(
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
                        emit_key_log(log, f"已切换模式 user={mask_user_openid(user_openid)} mode={next_mode}")
                        reply_text_for_user(
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
                        emit_key_log(log, f"进入场景稿注入等待态 user={mask_user_openid(user_openid)}")
                        reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=build_developer_input_text(task_running=service_busy),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    if interpretation_kind == "invalid_scene_draft":
                        reply_text_for_user(
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
                        result = accept_scene_draft_generation(
                            project_dir=project_dir,
                            job_queue=job_queue,
                            service_runtime=service_runtime,
                            service_runtime_lock=service_runtime_lock,
                            user_openid=user_openid,
                            scene_draft=scene_draft,
                            scene_draft_path=scene_draft_path,
                            source_message_id=source_message_id,
                        )
                        if not result.get("accepted"):
                            if str(result.get("reason", "")).strip() == "user_inflight":
                                emit_key_log(log, f"拒绝重复场景稿任务 user={mask_user_openid(user_openid)} reason=user_inflight")
                                reply_text_for_user(
                                    project_dir=project_dir,
                                    credentials=credentials,
                                    user_openid=user_openid,
                                    text_content=build_existing_task_reply_text(
                                        project_dir,
                                        mode=MODE_DEVELOPER,
                                        user_openid=user_openid,
                                        job_queue=job_queue,
                                    ),
                                    source_message_id=source_message_id,
                                    msg_seq=1,
                                )
                                continue
                            if str(result.get("reason", "")).strip() == "slot_busy":
                                emit_key_log(log, f"拒绝新的场景稿任务 user={mask_user_openid(user_openid)} reason=slot_busy")
                                reply_text_for_user(
                                    project_dir=project_dir,
                                    credentials=credentials,
                                    user_openid=user_openid,
                                    text_content=build_external_slot_busy_text(
                                        str((result.get("holder") or {}).get("busyMessage", "")).strip(),
                                        mode=MODE_DEVELOPER,
                                    ),
                                    source_message_id=source_message_id,
                                    msg_seq=1,
                                )
                                continue
                            emit_key_log(log, f"拒绝新的场景稿任务 user={mask_user_openid(user_openid)} reason=queue_full")
                            reply_text_for_user(
                                project_dir=project_dir,
                                credentials=credentials,
                                user_openid=user_openid,
                                text_content=build_queue_full_text(int(result.get("queueSize", 0) or 0)),
                                source_message_id=source_message_id,
                                msg_seq=1,
                            )
                            continue
                        set_private_user_pending_action(project_dir, user_openid, PENDING_ACTION_SCENE_DRAFT)
                        emit_key_log(log, f"已接收场景稿任务 user={mask_user_openid(user_openid)} path={scene_draft_path.name}")
                        reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=build_enqueued_reply_text(
                                result,
                                mode=MODE_DEVELOPER,
                                base_text=build_developer_input_received_text(
                                    scene_draft.get("scenePremiseZh", ""),
                                    queued=True,
                                ),
                            ),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    if interpretation_kind == "wrong_mode_command":
                        reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=str(interpretation["replyText"]),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    if interpretation_kind == "unknown":
                        reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=str(interpretation["replyText"]),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    if interpretation_kind != "trigger_generation":
                        reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=str(interpretation["replyText"]),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue

                    result = accept_full_generation(
                        project_dir=project_dir,
                        job_queue=job_queue,
                        service_runtime=service_runtime,
                        service_runtime_lock=service_runtime_lock,
                        user_openid=user_openid,
                        source_message_id=source_message_id,
                    )
                    if not result.get("accepted"):
                        if str(result.get("reason", "")).strip() == "user_inflight":
                            emit_key_log(log, f"拒绝重复生成请求 user={mask_user_openid(user_openid)} reason=user_inflight")
                            reply_text_for_user(
                                project_dir=project_dir,
                                credentials=credentials,
                                user_openid=user_openid,
                                text_content=build_existing_task_reply_text(
                                    project_dir,
                                    mode=normalize_private_mode(str(interpretation.get("nextMode", current_mode))),
                                    user_openid=user_openid,
                                    job_queue=job_queue,
                                ),
                                source_message_id=source_message_id,
                                msg_seq=1,
                            )
                            continue
                        if str(result.get("reason", "")).strip() == "slot_busy":
                            emit_key_log(log, f"拒绝新的生成请求 user={mask_user_openid(user_openid)} reason=slot_busy")
                            reply_text_for_user(
                                project_dir=project_dir,
                                credentials=credentials,
                                user_openid=user_openid,
                                text_content=build_external_slot_busy_text(
                                    str((result.get("holder") or {}).get("busyMessage", "")).strip(),
                                    mode=normalize_private_mode(str(interpretation.get("nextMode", current_mode))),
                                ),
                                source_message_id=source_message_id,
                                msg_seq=1,
                            )
                            continue
                        emit_key_log(log, f"拒绝新的生成请求 user={mask_user_openid(user_openid)} reason=queue_full")
                        reply_text_for_user(
                            project_dir=project_dir,
                            credentials=credentials,
                            user_openid=user_openid,
                            text_content=build_queue_full_text(int(result.get("queueSize", 0) or 0)),
                            source_message_id=source_message_id,
                            msg_seq=1,
                        )
                        continue
                    emit_key_log(log, f"已排队生成请求 user={mask_user_openid(user_openid)}")
                    reply_text_for_user(
                        project_dir=project_dir,
                        credentials=credentials,
                        user_openid=user_openid,
                        text_content=build_enqueued_reply_text(
                            result,
                            mode=normalize_private_mode(str(interpretation.get("nextMode", current_mode))),
                        ),
                        source_message_id=source_message_id,
                        msg_seq=1,
                    )
            except ServiceShutdownRequested:
                shutdown_requested = True
                stop_event.set()
                stop_payload = read_service_stop_request(project_dir) or {}
                mark_shutdown_requested(
                    project_dir=project_dir,
                    service_runtime=service_runtime,
                    service_runtime_lock=service_runtime_lock,
                    job_queue=job_queue,
                    reason=str(stop_payload.get("reason", "")).strip() or "shutdown requested",
                )
                while True:
                    runtime_snapshot = snapshot_service_runtime(service_runtime, service_runtime_lock)
                    has_active_run = bool(runtime_snapshot.get("activeRunId")) or bool(runtime_snapshot.get("reserved"))
                    has_queued_task = job_queue.pending_count() > 0
                    if not has_active_run and not has_queued_task:
                        break
                    time.sleep(0.5)
                break
            except (RuntimeError, WebSocketConnectionClosedException, OSError) as exc:
                if ready_only:
                    raise RuntimeError(str(exc)) from exc
                write_stage_status(
                    project_dir=project_dir,
                    status="reconnecting",
                    stage="gateway_reconnecting",
                    queued_count=job_queue.pending_count(),
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
        runtime_snapshot = snapshot_service_runtime(service_runtime, service_runtime_lock)
        append_service_event(
            project_dir,
            {
                "recordedAt": datetime.now().isoformat(timespec="seconds"),
                "type": "service_interrupt_requested",
                "runId": str(runtime_snapshot.get("activeRunId") or "").strip(),
                "stage": str(runtime_snapshot.get("currentStage") or "").strip(),
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
        )
    finally:
        stop_event.set()
        try:
            worker.join(timeout=1.5)
        except Exception:
            pass
        runtime_snapshot = snapshot_service_runtime(service_runtime, service_runtime_lock)
        append_service_event(
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
        write_stage_status(
            project_dir=project_dir,
            status="stopped",
            stage="shutdown_complete"
            if (interrupted or shutdown_requested)
            else str(runtime_snapshot.get("currentStage") or "").strip() or "stopped",
            user_openid=str(runtime_snapshot.get("activeUserOpenId") or "").strip(),
            source_message_id=str(runtime_snapshot.get("activeSourceMessageId") or "").strip(),
            run_id=str(runtime_snapshot.get("activeRunId") or "").strip(),
            queued_count=job_queue.pending_count(),
        )
        clear_service_stop_request(project_dir)
        release_service_lock(lock_path)
