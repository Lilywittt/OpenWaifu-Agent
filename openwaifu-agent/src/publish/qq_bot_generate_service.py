from __future__ import annotations

from . import qq_bot_runtime_store as _runtime_store
from .qq_bot_executor import (
    build_dynamic_publish_target as _build_dynamic_publish_target,
    build_dynamic_reply_target as _build_dynamic_reply_target,
    reply_text_for_user as _reply_text_for_user,
)
from .qq_bot_private_ui import build_help_text as _build_help_text_ui
from .qq_bot_ingress import recv_gateway_payload as _recv_gateway_payload
from .qq_bot_router import (
    COMMAND_ALIASES,
    DEFAULT_DEVELOPER_MODE_COMMAND,
    DEFAULT_DEVELOPER_SCENE_COMMAND,
    DEFAULT_EXPERIENCE_MODE_COMMAND,
    DEFAULT_HELP_COMMAND,
    DEFAULT_STATUS_COMMAND,
    DEFAULT_TRIGGER_COMMAND,
    canonicalize_command_text as _canonicalize_command_text,
    interpret_private_message as _interpret_private_message,
    is_known_command_alias as _is_known_command_alias,
    matches_command_alias as _matches_command_alias,
    normalize_message_text as _normalize_message_text,
)
from .qq_bot_runtime_store import (
    QQGenerateServiceAlreadyRunningError,
    cleanup_stale_service_lock,
    clear_service_stop_request,
    is_service_running,
    load_latest_known_user_openid as _load_latest_known_user_openid,
    qq_bot_generate_service_state_root,
    read_service_lock,
    read_service_pid,
    read_service_status,
    read_service_stop_request,
    request_service_stop,
    _is_process_alive,
)
from .qq_bot_service import (
    DEFAULT_RECONNECT_DELAY_SECONDS,
    DEFAULT_WS_RECV_TIMEOUT_SECONDS,
    run_qq_bot_generate_service,
    task_worker as _task_worker,
)
from .qq_bot_service_support import (
    MAX_HANDLED_MESSAGE_IDS,
    emit_key_log as _emit_key_log,
    mask_user_openid as _mask_user_openid,
    remember_handled_message as _remember_handled_message,
)
from .qq_bot_task_policy import (
    accept_full_generation as _accept_full_generation,
    accept_scene_draft_generation as _accept_scene_draft_generation,
    build_busy_text as _build_busy_text,
    build_busy_text_for_mode as _build_busy_text_for_mode,
    build_enqueued_reply_text as _build_enqueued_reply_text,
    build_existing_task_reply_text as _build_existing_task_reply_text,
    build_failed_text as _build_failed_text,
    build_help_text as _build_help_text,
    build_scene_draft_busy_reply as _build_scene_draft_busy_reply,
    build_started_text as _build_started_text,
    build_status_text as _build_status_text,
    clear_busy_reply_tracking as _clear_busy_reply_tracking,
    current_status_payload as _current_status_payload,
    enqueue_generation_task as _enqueue_generation_task,
    is_interrupt_requested as _is_interrupt_requested,
    service_is_busy as _service_is_busy,
    should_reply_busy_once as _should_reply_busy_once,
    user_mode as _user_mode,
    write_queue_accept_status as _write_queue_accept_status,
)

__all__ = [
    "COMMAND_ALIASES",
    "DEFAULT_DEVELOPER_MODE_COMMAND",
    "DEFAULT_DEVELOPER_SCENE_COMMAND",
    "DEFAULT_EXPERIENCE_MODE_COMMAND",
    "DEFAULT_HELP_COMMAND",
    "DEFAULT_RECONNECT_DELAY_SECONDS",
    "DEFAULT_STATUS_COMMAND",
    "DEFAULT_TRIGGER_COMMAND",
    "DEFAULT_WS_RECV_TIMEOUT_SECONDS",
    "MAX_HANDLED_MESSAGE_IDS",
    "QQGenerateServiceAlreadyRunningError",
    "_accept_full_generation",
    "_accept_scene_draft_generation",
    "_acquire_service_lock",
    "_build_busy_text",
    "_build_busy_text_for_mode",
    "_build_dynamic_publish_target",
    "_build_dynamic_reply_target",
    "_build_enqueued_reply_text",
    "_build_existing_task_reply_text",
    "_build_failed_text",
    "_build_help_text",
    "_build_scene_draft_busy_reply",
    "_build_started_text",
    "_build_status_text",
    "_canonicalize_command_text",
    "_clear_busy_reply_tracking",
    "_current_status_payload",
    "_emit_key_log",
    "_enqueue_generation_task",
    "_interpret_private_message",
    "_is_interrupt_requested",
    "_is_known_command_alias",
    "_is_process_alive",
    "_load_latest_known_user_openid",
    "_mask_user_openid",
    "_matches_command_alias",
    "_normalize_message_text",
    "_recv_gateway_payload",
    "_reply_text_for_user",
    "_release_service_lock",
    "_remember_handled_message",
    "_send_startup_guidance_if_possible",
    "_service_is_busy",
    "_should_reply_busy_once",
    "_task_worker",
    "_user_mode",
    "_write_queue_accept_status",
    "cleanup_stale_service_lock",
    "clear_service_stop_request",
    "is_service_running",
    "qq_bot_generate_service_state_root",
    "read_service_lock",
    "read_service_pid",
    "read_service_status",
    "read_service_stop_request",
    "request_service_stop",
    "run_qq_bot_generate_service",
]


def _send_startup_guidance_if_possible(
    *,
    project_dir,
    credentials,
    trigger_command,
    help_command,
    status_command,
    log,
):
    user_openid = _load_latest_known_user_openid(project_dir)
    if not user_openid:
        _emit_key_log(log, "启动后未找到已知用户，暂不主动推送指引。")
        return False
    _reply_text_for_user(
        project_dir=project_dir,
        credentials=credentials,
        user_openid=user_openid,
        text_content=_build_help_text_ui(trigger_command, help_command, status_command, mode=_user_mode(project_dir, user_openid)),
    )
    return True


def _acquire_service_lock(project_dir):
    _runtime_store._is_process_alive = _is_process_alive
    return _runtime_store.acquire_service_lock(project_dir)


def _release_service_lock(lock_path):
    _runtime_store._is_process_alive = _is_process_alive
    return _runtime_store.release_service_lock(lock_path)
