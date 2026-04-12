from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from product_pipeline import run_full_product_pipeline, run_scene_draft_full_pipeline
from runtime_layout import create_run_bundle, sanitize_segment

from .qq_bot_client import fetch_app_access_token, send_text_message
from .qq_bot_private_ui import build_help_text as build_help_text_ui
from .qq_bot_runtime_store import append_service_event, load_latest_known_user_openid
from .qq_bot_service_support import emit_key_log, mask_user_openid


TOKEN_CACHE: dict[str, dict[str, Any]] = {}
TOKEN_CACHE_LOCK = threading.Lock()


def scene_draft_source_meta(scene_draft_path: Path, *, user_openid: str) -> dict[str, Any]:
    return {
        "sceneDraftPath": str(scene_draft_path),
        "sourceType": "qq_bot_developer_mode",
        "userOpenId": str(user_openid).strip(),
    }


def build_dynamic_publish_target(user_openid: str) -> dict[str, Any]:
    return {
        "targetId": "qq_bot_user_dynamic",
        "adapter": "qq_bot_user",
        "displayName": "QQ Bot User Dynamic",
        "scene": "user",
        "targetOpenId": str(user_openid).strip(),
    }


def build_dynamic_reply_target(
    *,
    user_openid: str,
    source_message_id: str = "",
    reply_message_seq: int = 0,
    reply_event_id: str = "",
) -> dict[str, Any]:
    target = build_dynamic_publish_target(user_openid)
    if source_message_id:
        target["replyMessageId"] = source_message_id
    if reply_message_seq:
        target["replyMessageSeq"] = int(reply_message_seq)
    if reply_event_id:
        target["replyEventId"] = reply_event_id
    return target


def resolve_cached_access_token(credentials: dict[str, Any]) -> str:
    app_id = str(credentials.get("appId", "")).strip()
    access_token_url = str(credentials.get("accessTokenUrl", "")).strip()
    cache_key = f"{app_id}:{access_token_url}"
    now = time.time()
    with TOKEN_CACHE_LOCK:
        cached = TOKEN_CACHE.get(cache_key)
        if cached and cached.get("expiresAt", 0) > now:
            return str(cached.get("accessToken", "")).strip()

    token_response = fetch_app_access_token(
        app_id=credentials["appId"],
        app_secret=credentials["appSecret"],
        access_token_url=credentials["accessTokenUrl"],
        timeout_ms=credentials["timeoutMs"],
    )
    access_token = str(token_response["access_token"]).strip()
    expires_in = int(token_response.get("expires_in", 0) or 0)
    ttl_seconds = max(expires_in - 60, 60) if expires_in > 0 else 300
    with TOKEN_CACHE_LOCK:
        TOKEN_CACHE[cache_key] = {
            "accessToken": access_token,
            "expiresAt": now + ttl_seconds,
        }
    return access_token


def reply_text_for_user(
    *,
    project_dir: Path,
    credentials: dict[str, Any],
    user_openid: str,
    text_content: str,
    source_message_id: str = "",
    msg_seq: int = 0,
    event_id: str = "",
) -> dict[str, Any]:
    access_token = resolve_cached_access_token(credentials)
    return send_text_message(
        access_token=access_token,
        api_base_url=credentials["apiBaseUrl"],
        scene="user",
        target_openid=user_openid,
        content=text_content,
        timeout_ms=credentials["timeoutMs"],
        msg_id=source_message_id,
        msg_seq=msg_seq,
        event_id=event_id,
    )


def send_startup_guidance_if_possible(
    *,
    project_dir: Path,
    credentials: dict[str, Any],
    trigger_command: str,
    help_command: str,
    status_command: str,
    user_mode_loader: Callable[[Path, str], str],
    log: Callable[[str], None] | None,
) -> bool:
    user_openid = load_latest_known_user_openid(project_dir)
    if not user_openid:
        emit_key_log(log, "启动后未找到已知用户，暂不主动推送指引。")
        return False

    user_mode = user_mode_loader(project_dir, user_openid)
    help_text = build_help_text_ui(trigger_command, help_command, status_command, mode=user_mode)
    try:
        reply_text_for_user(
            project_dir=project_dir,
            credentials=credentials,
            user_openid=user_openid,
            text_content=help_text,
        )
    except Exception as exc:
        append_service_event(
            project_dir,
            {
                "recordedAt": datetime.now().isoformat(timespec="seconds"),
                "type": "startup_guidance_failed",
                "userOpenId": user_openid,
                "error": str(exc),
            },
        )
        emit_key_log(log, f"启动指引推送失败 user={mask_user_openid(user_openid)} error={str(exc)[:120]}")
        return False

    append_service_event(
        project_dir,
        {
            "recordedAt": datetime.now().isoformat(timespec="seconds"),
            "type": "startup_guidance_sent",
            "userOpenId": user_openid,
            "mode": user_mode,
        },
    )
    emit_key_log(log, f"启动指引已推送给 user={mask_user_openid(user_openid)} mode={user_mode}")
    return True


def run_generation_task(
    *,
    project_dir: Path,
    bundle,
    task: dict[str, Any],
    log: Callable[[str], None] | None,
    should_abort: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    user_openid = str(task.get("userOpenId", "")).strip()
    source_message_id = str(task.get("sourceMessageId", "")).strip()
    reply_event_id = str(task.get("replyEventId", "")).strip()
    publish_targets = [
        build_dynamic_reply_target(
            user_openid=user_openid,
            source_message_id=source_message_id,
            reply_message_seq=2 if source_message_id else 0,
            reply_event_id=reply_event_id,
        )
    ]
    task_type = str(task.get("taskType", "full_generation")).strip()
    generation_owner = {
        "ownerType": "qq_bot_service",
        "ownerLabel": "QQ 私聊服务",
        "runId": str(bundle.run_id),
        "metadata": {
            "taskType": task_type,
            "userOpenId": user_openid,
        },
    }
    if task_type == "scene_draft_to_image":
        return run_scene_draft_full_pipeline(
            project_dir,
            bundle,
            scene_draft=dict(task["sceneDraft"]),
            source_meta=scene_draft_source_meta(Path(str(task["sceneDraftPath"])), user_openid=user_openid),
            log=log,
            explicit_publish_targets=publish_targets,
            should_abort=should_abort,
            generation_owner=generation_owner,
        )
    return run_full_product_pipeline(
        project_dir,
        bundle,
        log=log,
        explicit_publish_targets=publish_targets,
        should_abort=should_abort,
        generation_owner=generation_owner,
    )


def create_generation_bundle(project_dir: Path, *, task_type: str, user_openid: str):
    run_prefix = "qqbot_scene" if task_type == "scene_draft_to_image" else "qqbot_generate"
    run_label = f"{run_prefix}_{sanitize_segment(str(user_openid)[:8].lower())}"
    return create_run_bundle(project_dir, "generate", run_label)
