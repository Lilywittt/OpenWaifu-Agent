from __future__ import annotations

import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from ..chat_service import CharacterChatService
from ..config import load_app_config
from ..image_bridge import OpenWaifuAgentBridge
from ..router import (
    MODE_CHAT,
    MODE_IMAGE,
    interpret_message,
    save_user_state,
)
from ..runtime_store import (
    ServiceShutdownRequested,
    acquire_service_lock,
    append_service_event,
    clear_service_stop_request,
    read_service_stop_request,
    release_service_lock,
    write_service_status,
)
from .client import load_qq_config, resolve_qq_credentials, send_text_message
from .gateway import connect_gateway, recv_gateway_payload, save_gateway_event, save_gateway_status
from .identity import extract_user_openid, persist_latest_user_openid


DEFAULT_WS_RECV_TIMEOUT_SECONDS = 2.0
MAX_HANDLED_MESSAGE_IDS = 500


def mask_user_openid(user_openid: str) -> str:
    text = str(user_openid or "").strip()
    if not text:
        return "unknown"
    if len(text) <= 8:
        return text
    return f"{text[:4]}...{text[-4:]}"


def remember_handled_message(source_message_id: str, handled_ids: set[str], handled_order: deque[str]) -> None:
    if not source_message_id or source_message_id in handled_ids:
        return
    handled_ids.add(source_message_id)
    handled_order.append(source_message_id)
    while len(handled_order) > MAX_HANDLED_MESSAGE_IDS:
        stale = handled_order.popleft()
        handled_ids.discard(stale)


def emit_log(log: Callable[[str], None] | None, message: str) -> None:
    if log is not None:
        log(f"[roleplay-qq] {message}")


def _reply(
    *,
    project_dir: Path,
    credentials: dict,
    user_openid: str,
    text: str,
    source_message_id: str = "",
    msg_seq: int = 1,
    log: Callable[[str], None] | None = None,
) -> None:
    try:
        send_text_message(
            credentials=credentials,
            user_openid=user_openid,
            content=text,
            msg_id=source_message_id,
            msg_seq=msg_seq if source_message_id else 0,
        )
    except Exception as exc:  # noqa: BLE001
        append_service_event(
            project_dir,
            {
                "type": "reply_failed",
                "userOpenId": user_openid,
                "sourceMessageId": source_message_id,
                "error": str(exc),
            },
        )
        emit_log(log, f"回复失败 user={mask_user_openid(user_openid)} error={str(exc)[:160]}")


def _handle_chat_message(
    *,
    project_dir: Path,
    chat_service: CharacterChatService,
    credentials: dict,
    user_openid: str,
    source_message_id: str,
    content: str,
    log: Callable[[str], None] | None,
) -> None:
    try:
        reply = chat_service.generate_reply(user_id=user_openid, user_text=content)
    except Exception as exc:  # noqa: BLE001
        append_service_event(
            project_dir,
            {
                "type": "chat_failed",
                "userOpenId": user_openid,
                "sourceMessageId": source_message_id,
                "error": str(exc),
            },
        )
        reply = f"我这边调用聊天模型失败了：{str(exc)[:180]}"
    _reply(
        project_dir=project_dir,
        credentials=credentials,
        user_openid=user_openid,
        text=reply,
        source_message_id=source_message_id,
        msg_seq=1,
        log=log,
    )


def _handle_route(
    *,
    project_dir: Path,
    route_kind: str,
    route_reply_text: str,
    next_mode: str,
    next_pending: str,
    route_payload: dict | None,
    chat_service: CharacterChatService,
    image_bridge: OpenWaifuAgentBridge,
    credentials: dict,
    user_openid: str,
    source_message_id: str,
    content: str,
    log: Callable[[str], None] | None,
) -> None:
    if route_kind == "chat":
        _handle_chat_message(
            project_dir=project_dir,
            chat_service=chat_service,
            credentials=credentials,
            user_openid=user_openid,
            source_message_id=source_message_id,
            content=str((route_payload or {}).get("text", content)),
            log=log,
        )
        return

    if route_kind == "reset_conversation":
        chat_service.reset_conversation(user_openid)
        _reply(
            project_dir=project_dir,
            credentials=credentials,
            user_openid=user_openid,
            text=route_reply_text,
            source_message_id=source_message_id,
            log=log,
        )
        return

    if route_kind in {"enter_image_mode", "exit_image_mode", "image_scene_prompt"}:
        save_user_state(project_dir, user_openid, mode=next_mode, pending_action=next_pending)
        _reply(
            project_dir=project_dir,
            credentials=credentials,
            user_openid=user_openid,
            text=route_reply_text,
            source_message_id=source_message_id,
            log=log,
        )
        return

    if route_kind in {"help", "status", "reload_config", "image_mode_unknown"}:
        _reply(
            project_dir=project_dir,
            credentials=credentials,
            user_openid=user_openid,
            text=route_reply_text,
            source_message_id=source_message_id,
            log=log,
        )
        return

    if route_kind == "image_generate":
        save_user_state(project_dir, user_openid, mode=MODE_IMAGE, pending_action="")
        try:
            accepted = image_bridge.enqueue_default_generation(
                user_openid=user_openid,
                source_message_id=source_message_id,
            )
        except Exception as exc:  # noqa: BLE001
            _reply(
                project_dir=project_dir,
                credentials=credentials,
                user_openid=user_openid,
                text=f"生图桥接暂时不可用：{str(exc)[:180]}",
                source_message_id=source_message_id,
                log=log,
            )
            return
        text = "已加入生图队列，完成后会发回图片。" if accepted else "生图队列正在忙，请稍后再发。"
        _reply(
            project_dir=project_dir,
            credentials=credentials,
            user_openid=user_openid,
            text=text,
            source_message_id=source_message_id,
            log=log,
        )
        return

    if route_kind == "image_scene_submit":
        save_user_state(project_dir, user_openid, mode=MODE_IMAGE, pending_action=next_pending)
        scene_text = str((route_payload or {}).get("sceneText", "")).strip()
        try:
            image_bridge.validate_scene_draft_text(scene_text)
            accepted = image_bridge.enqueue_scene_generation(
                user_openid=user_openid,
                scene_text=scene_text,
                source_message_id=source_message_id,
            )
        except Exception as exc:  # noqa: BLE001
            _reply(
                project_dir=project_dir,
                credentials=credentials,
                user_openid=user_openid,
                text=f"场景稿没有通过解析：{str(exc)[:220]}",
                source_message_id=source_message_id,
                log=log,
            )
            return
        text = "场景稿已加入生图队列，完成后会发回图片。" if accepted else "生图队列正在忙，请稍后再发。"
        _reply(
            project_dir=project_dir,
            credentials=credentials,
            user_openid=user_openid,
            text=text,
            source_message_id=source_message_id,
            log=log,
        )
        return

    _reply(
        project_dir=project_dir,
        credentials=credentials,
        user_openid=user_openid,
        text=route_reply_text or "这条消息没有匹配到可执行动作。",
        source_message_id=source_message_id,
        log=log,
    )


def run_qq_publish_outlet(
    project_dir: Path,
    *,
    config_path: Path | None = None,
    ready_only: bool = False,
    wait_seconds: int = 0,
    reconnect_delay_seconds: float = 3.0,
    skip_legacy_service_check: bool = False,
    log: Callable[[str], None] | None = None,
) -> None:
    lock_path = acquire_service_lock(project_dir)
    clear_service_stop_request(project_dir)
    app_config = load_app_config(project_dir)
    qq_config = load_qq_config(project_dir, config_path)
    credentials = resolve_qq_credentials(project_dir, qq_config)
    chat_service = CharacterChatService(project_dir)
    image_bridge = OpenWaifuAgentBridge(project_dir, log=log)
    if not skip_legacy_service_check:
        image_bridge.assert_preflight_ok()

    max_workers = max(int(app_config.get("qqService", {}).get("maxReplyWorkers", 3)), 1)
    executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="roleplay-qq-reply")
    handled_ids: set[str] = set()
    handled_order: deque[str] = deque()
    started_at = time.time()
    write_service_status(project_dir, status="starting", stage="initializing")

    try:
        while True:
            if read_service_stop_request(project_dir):
                raise ServiceShutdownRequested()
            if not ready_only and wait_seconds > 0 and time.time() - started_at >= wait_seconds:
                raise RuntimeError(f"Timed out after {wait_seconds} seconds waiting for QQ messages.")

            ws = None
            connection_state = None
            try:
                ws, connection_state = connect_gateway(credentials)
                gateway_url = str(connection_state["gatewayInfo"]["url"])
                timeout_exception = connection_state["timeoutException"]
                emit_log(log, "网关已连接，正在监听 QQ 私聊。")
                write_service_status(project_dir, status="listening", stage="waiting_for_message")
                while True:
                    if read_service_stop_request(project_dir):
                        raise ServiceShutdownRequested()
                    raw_message, payload = recv_gateway_payload(
                        ws,
                        timeout_seconds=DEFAULT_WS_RECV_TIMEOUT_SECONDS,
                        timeout_exception=timeout_exception,
                    )
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
                    if source_message_id and source_message_id in handled_ids:
                        continue
                    remember_handled_message(source_message_id, handled_ids, handled_order)
                    if payload.get("d", {}).get("author", {}).get("bot"):
                        continue
                    user_openid = extract_user_openid(payload)
                    if not user_openid:
                        continue
                    event_path = save_gateway_event(project_dir, payload=payload, raw_message=raw_message)
                    persist_latest_user_openid(project_dir, user_openid=user_openid, event_path=event_path)
                    content = str(payload.get("d", {}).get("content", "")).strip()
                    route = interpret_message(
                        project_dir=project_dir,
                        user_id=user_openid,
                        content=content,
                        image_bridge_status=image_bridge.status_text(),
                    )
                    emit_log(log, f"收到私聊 user={mask_user_openid(user_openid)} action={route.kind}")
                    executor.submit(
                        _handle_route,
                        project_dir=project_dir,
                        route_kind=route.kind,
                        route_reply_text=route.reply_text,
                        next_mode=route.next_mode,
                        next_pending=route.next_pending,
                        route_payload=route.payload,
                        chat_service=chat_service,
                        image_bridge=image_bridge,
                        credentials=credentials,
                        user_openid=user_openid,
                        source_message_id=source_message_id,
                        content=content,
                        log=log,
                    )
            except ServiceShutdownRequested:
                raise
            except Exception as exc:  # noqa: BLE001
                if ready_only:
                    raise
                append_service_event(project_dir, {"type": "gateway_reconnect", "error": str(exc)})
                write_service_status(project_dir, status="reconnecting", stage="gateway_reconnecting", error=str(exc))
                emit_log(log, f"连接异常，{reconnect_delay_seconds:.1f} 秒后重连：{exc}")
                time.sleep(max(float(reconnect_delay_seconds), 1.0))
            finally:
                if connection_state is not None:
                    connection_state["state"]["running"] = False
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass
    except ServiceShutdownRequested:
        append_service_event(project_dir, {"type": "service_stop_requested"})
        write_service_status(project_dir, status="stopping", stage="shutdown_requested")
    finally:
        executor.shutdown(wait=False, cancel_futures=False)
        write_service_status(project_dir, status="stopped", stage="shutdown_complete")
        clear_service_stop_request(project_dir)
        release_service_lock(lock_path)
