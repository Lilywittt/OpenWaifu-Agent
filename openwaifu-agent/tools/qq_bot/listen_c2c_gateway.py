from __future__ import annotations

"""通过 QQ bot WebSocket 网关监听私聊事件，自动抓取 user_openid，并按需持续回声回复。"""

import argparse
import json
import sys
import threading
import time
from pathlib import Path

import websocket
from websocket._exceptions import WebSocketConnectionClosedException, WebSocketTimeoutException

PROJECT_DIR = Path(__file__).resolve().parents[2]
TOOLS_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
for import_path in (TOOLS_DIR, SRC_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from common import build_tool_run_dir, configure_utf8_stdio

from io_utils import ensure_dir, write_json, write_text
from publish.qq_bot_client import (
    fetch_app_access_token,
    load_qq_bot_message_config,
    resolve_qq_bot_credentials,
    send_media_message,
    send_text_message,
    upload_rich_media,
)
from publish.qq_bot_gateway import (
    QQ_BOT_C2C_INTENT,
    build_gateway_heartbeat_payload,
    build_gateway_identify_payload,
    fetch_gateway_info,
    persist_user_openid,
    save_gateway_event,
    save_gateway_status,
)
from publish.qq_bot_identity import extract_user_openid


TOOL_KIND = "qq_bot_c2c_gateway"
DEFAULT_WS_RECV_TIMEOUT_SECONDS = 2.0
DEFAULT_RECONNECT_DELAY_SECONDS = 3.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Listen for QQ bot C2C messages over the WebSocket gateway, capture user_openid, and optionally echo replies."
    )
    parser.add_argument("--label", default="qqbot_c2c_gateway")
    parser.add_argument("--config", default=str(PROJECT_DIR / "config" / "publish" / "qq_bot_message.json"))
    parser.add_argument("--wait-seconds", type=int, default=300)
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--ready-only", action="store_true")
    parser.add_argument("--no-auto-reply", action="store_true")
    parser.add_argument("--reply-content", default="")
    parser.add_argument("--reconnect-delay-seconds", type=float, default=DEFAULT_RECONNECT_DELAY_SECONDS)
    return parser


def _write_runner_input(
    batch_dir: Path,
    *,
    config_path: str,
    wait_seconds: int,
    continuous: bool,
    ready_only: bool,
    auto_reply: bool,
    reply_content: str,
    reconnect_delay_seconds: float,
) -> None:
    write_json(
        batch_dir / "00_runner_input.json",
        {
            "configPath": str(Path(config_path).resolve()),
            "waitSeconds": wait_seconds,
            "continuous": continuous,
            "readyOnly": ready_only,
            "autoReply": auto_reply,
            "replyContent": reply_content,
            "reconnectDelaySeconds": reconnect_delay_seconds,
        },
    )


def _recv_gateway_payload(ws: websocket.WebSocket, *, timeout_seconds: float) -> tuple[str | None, dict | None]:
    previous_timeout = ws.gettimeout()
    ws.settimeout(timeout_seconds)
    try:
        raw_message = ws.recv()
    except WebSocketTimeoutException:
        return None, None
    finally:
        ws.settimeout(previous_timeout)
    return raw_message, json.loads(raw_message)


def _resolve_auto_reply_content(payload: dict, manual_reply_content: str) -> str:
    manual = str(manual_reply_content or "").strip()
    if manual:
        return manual
    event_content = str(payload.get("d", {}).get("content", "")).strip()
    if event_content:
        return event_content
    return "已收到你的私聊。"


def _append_jsonl(path: Path, payload: dict) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _normalize_attachment_url(raw_url: str) -> str:
    resolved_url = str(raw_url or "").strip()
    if resolved_url.startswith("//"):
        return f"https:{resolved_url}"
    return resolved_url


def _resolve_attachment_file_type(content_type: str) -> int:
    normalized = str(content_type or "").strip().lower()
    if normalized.startswith("image/"):
        return 1
    if normalized.startswith("video/"):
        return 2
    if normalized.startswith("audio/"):
        return 3
    return 4


def _extract_media_specs(payload: dict) -> list[dict]:
    attachments = payload.get("d", {}).get("attachments", [])
    if not isinstance(attachments, list):
        return []
    media_specs: list[dict] = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        attachment_url = _normalize_attachment_url(str(attachment.get("url", "")).strip())
        if not attachment_url:
            continue
        content_type = str(attachment.get("content_type", "")).strip()
        media_specs.append(
            {
                "url": attachment_url,
                "contentType": content_type,
                "fileType": _resolve_attachment_file_type(content_type),
                "name": str(attachment.get("name", "")).strip(),
            }
        )
    return media_specs


def _connect_gateway(credentials: dict, token_response: dict, batch_dir: Path) -> tuple[websocket.WebSocket, dict]:
    gateway_info = fetch_gateway_info(
        app_id=credentials["appId"],
        access_token=str(token_response["access_token"]),
        api_base_url=credentials["apiBaseUrl"],
        timeout_ms=credentials["timeoutMs"],
    )
    write_json(batch_dir / "02_gateway_info.json", gateway_info)

    connect_timeout_seconds = max(credentials["timeoutMs"], 1000) / 1000.0
    ws = websocket.create_connection(str(gateway_info["url"]), timeout=connect_timeout_seconds)
    hello_payload = json.loads(ws.recv())
    write_json(batch_dir / "03_hello.json", hello_payload)
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
        intents=QQ_BOT_C2C_INTENT,
    )
    write_json(batch_dir / "04_identify_payload.json", identify_payload)
    ws.send(json.dumps(identify_payload, ensure_ascii=False))
    return ws, {"gatewayInfo": gateway_info, "state": state}


def _reply_with_text(
    *,
    batch_dir: Path,
    message_index: int,
    reply_index: int,
    token_response: dict,
    credentials: dict,
    target_openid: str,
    content: str,
    source_message_id: str,
) -> str:
    message_response = send_text_message(
        access_token=str(token_response["access_token"]),
        api_base_url=credentials["apiBaseUrl"],
        scene="user",
        target_openid=target_openid,
        content=content,
        timeout_ms=credentials["timeoutMs"],
        msg_id=source_message_id,
        msg_seq=reply_index,
    )
    sanitized = dict(message_response)
    sanitized.pop("_request", None)
    response_path = batch_dir / f"07_auto_reply_response_{message_index:04d}_{reply_index:02d}.json"
    write_json(response_path, sanitized)
    return str(response_path)


def _reply_with_media(
    *,
    batch_dir: Path,
    message_index: int,
    reply_index: int,
    token_response: dict,
    credentials: dict,
    target_openid: str,
    content: str,
    source_message_id: str,
    media_spec: dict,
) -> str:
    upload_result = upload_rich_media(
        access_token=str(token_response["access_token"]),
        api_base_url=credentials["apiBaseUrl"],
        scene="user",
        target_openid=target_openid,
        file_type=int(media_spec["fileType"]),
        url=str(media_spec["url"]),
        srv_send_msg=False,
        timeout_ms=credentials["timeoutMs"],
    )
    file_info = str(upload_result.get("file_info", "")).strip()
    if not file_info:
        raise RuntimeError(f"QQ bot rich media upload missing file_info: {upload_result}")

    message_response = send_media_message(
        access_token=str(token_response["access_token"]),
        api_base_url=credentials["apiBaseUrl"],
        scene="user",
        target_openid=target_openid,
        file_info=file_info,
        content=content,
        timeout_ms=credentials["timeoutMs"],
        msg_id=source_message_id,
        msg_seq=reply_index,
    )
    sanitized = dict(message_response)
    sanitized.pop("_request", None)
    payload = {
        "upload": {
            "request": upload_result.get("_request", {}),
            "fileUuid": upload_result.get("file_uuid", ""),
            "ttl": upload_result.get("ttl"),
            "contentType": media_spec.get("contentType", ""),
            "url": media_spec.get("url", ""),
        },
        "message": sanitized,
    }
    response_path = batch_dir / f"07_auto_reply_response_{message_index:04d}_{reply_index:02d}.json"
    write_json(response_path, payload)
    return str(response_path)


def _handle_c2c_message(
    *,
    payload: dict,
    raw_message: str,
    batch_dir: Path,
    message_index: int,
    auto_reply: bool,
    manual_reply_content: str,
    token_response: dict,
    credentials: dict,
) -> dict:
    captured_event_path = save_gateway_event(PROJECT_DIR, payload=payload, raw_message=raw_message)
    write_json(batch_dir / f"06_c2c_event_{message_index:04d}.json", payload)

    captured_openid = extract_user_openid(payload)
    if not captured_openid:
        raise RuntimeError(f"C2C event missing user_openid/id: {payload}")

    latest_user_path = persist_user_openid(
        PROJECT_DIR,
        user_openid=captured_openid,
        event_path=captured_event_path,
    )

    reply_paths: list[str] = []
    reply_content = ""
    media_specs = _extract_media_specs(payload)
    source_message_id = str(payload.get("d", {}).get("id", "")).strip()

    if auto_reply:
        reply_content = _resolve_auto_reply_content(payload, manual_reply_content)
        if media_specs:
            for reply_index, media_spec in enumerate(media_specs, start=1):
                reply_paths.append(
                    _reply_with_media(
                        batch_dir=batch_dir,
                        message_index=message_index,
                        reply_index=reply_index,
                        token_response=token_response,
                        credentials=credentials,
                        target_openid=captured_openid,
                        content=reply_content if reply_index == 1 else "",
                        source_message_id=source_message_id,
                        media_spec=media_spec,
                    )
                )
        else:
            reply_paths.append(
                _reply_with_text(
                    batch_dir=batch_dir,
                    message_index=message_index,
                    reply_index=1,
                    token_response=token_response,
                    credentials=credentials,
                    target_openid=captured_openid,
                    content=reply_content,
                    source_message_id=source_message_id,
                )
            )

    return {
        "messageIndex": message_index,
        "eventPath": str(captured_event_path),
        "latestUserPath": str(latest_user_path),
        "userOpenId": captured_openid,
        "replyContent": reply_content,
        "replyResponsePaths": reply_paths,
        "sourceMessageId": source_message_id,
        "mediaCount": len(media_specs),
    }


def run_once(
    *,
    label: str,
    config_path: str,
    wait_seconds: int,
    continuous: bool,
    ready_only: bool,
    auto_reply: bool,
    reply_content: str,
    reconnect_delay_seconds: float,
) -> Path:
    batch_dir = build_tool_run_dir(TOOL_KIND, label)
    ensure_dir(batch_dir)
    _write_runner_input(
        batch_dir,
        config_path=config_path,
        wait_seconds=wait_seconds,
        continuous=continuous,
        ready_only=ready_only,
        auto_reply=auto_reply,
        reply_content=reply_content,
        reconnect_delay_seconds=reconnect_delay_seconds,
    )

    config = load_qq_bot_message_config(PROJECT_DIR, Path(config_path).resolve())
    credentials = resolve_qq_bot_credentials(
        PROJECT_DIR,
        config,
        scene_override="user",
        target_openid_override="placeholder_user_openid",
    )
    token_response = fetch_app_access_token(
        app_id=credentials["appId"],
        app_secret=credentials["appSecret"],
        access_token_url=credentials["accessTokenUrl"],
        timeout_ms=credentials["timeoutMs"],
    )
    write_json(batch_dir / "01_access_token_response.json", {"expiresIn": token_response.get("expires_in")})

    started_at = time.time()
    handled_messages = 0
    latest_user_path = ""
    latest_event_path = ""
    latest_openid = ""
    last_gateway_url = ""
    message_log_path = batch_dir / "08_message_log.jsonl"
    handled_source_message_ids: set[str] = set()

    print("[qq-gateway] 网关监听准备完成。", flush=True)
    if ready_only:
        print("[qq-gateway] 当前为 ready-only 模式。", flush=True)
    elif continuous:
        print("[qq-gateway] 当前为持续监听模式。给机器人发私聊后会原样回声。", flush=True)
    else:
        print("[qq-gateway] 现在给机器人发一条私聊。", flush=True)

    while True:
        deadline_reached = (not continuous) and (time.time() - started_at >= wait_seconds)
        if deadline_reached:
            raise RuntimeError(f"Timed out after {wait_seconds} seconds waiting for C2C_MESSAGE_CREATE.")

        ws = None
        connection_state = None
        try:
            ws, connection_state = _connect_gateway(credentials, token_response, batch_dir)
            last_gateway_url = str(connection_state["gatewayInfo"]["url"])

            while True:
                deadline_reached = (not continuous) and (time.time() - started_at >= wait_seconds)
                if deadline_reached:
                    raise RuntimeError(f"Timed out after {wait_seconds} seconds waiting for C2C_MESSAGE_CREATE.")

                raw_message, payload = _recv_gateway_payload(ws, timeout_seconds=DEFAULT_WS_RECV_TIMEOUT_SECONDS)
                if raw_message is None or payload is None:
                    continue

                if "s" in payload:
                    connection_state["state"]["seq"] = payload.get("s")

                event_type = str(payload.get("t", "")).strip()
                if event_type == "READY":
                    write_json(batch_dir / "05_ready.json", payload)
                    session_id = str(payload.get("d", {}).get("session_id", "")).strip()
                    save_gateway_status(
                        PROJECT_DIR,
                        gateway_url=last_gateway_url,
                        session_id=session_id,
                        event_type=event_type,
                    )
                    if ready_only:
                        break
                    continue

                if event_type != "C2C_MESSAGE_CREATE":
                    continue

                source_message_id = str(payload.get("d", {}).get("id", "")).strip()
                if source_message_id and source_message_id in handled_source_message_ids:
                    continue
                if source_message_id:
                    handled_source_message_ids.add(source_message_id)

                handled_messages += 1
                result = _handle_c2c_message(
                    payload=payload,
                    raw_message=raw_message,
                    batch_dir=batch_dir,
                    message_index=handled_messages,
                    auto_reply=auto_reply,
                    manual_reply_content=reply_content,
                    token_response=token_response,
                    credentials=credentials,
                )
                latest_event_path = result["eventPath"]
                latest_user_path = result["latestUserPath"]
                latest_openid = result["userOpenId"]
                _append_jsonl(message_log_path, result)

                if not continuous:
                    break
        except (RuntimeError, WebSocketConnectionClosedException, OSError) as exc:
            if not continuous:
                raise RuntimeError(str(exc)) from exc
            print(f"[qq-gateway] 连接异常，{reconnect_delay_seconds:.1f} 秒后重连: {exc}", file=sys.stderr, flush=True)
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

        if ready_only:
            break
        if handled_messages > 0 and not continuous:
            break
        if not continuous:
            raise RuntimeError(f"Timed out after {wait_seconds} seconds waiting for C2C_MESSAGE_CREATE.")

    write_text(
        batch_dir / "complete_results.md",
        "\n".join(
            [
                "# QQ bot 私聊 openid 抓取结果",
                "",
                f"- 批次目录: `{batch_dir}`",
                f"- gateway: `{last_gateway_url}`",
                f"- readyOnly: `{ready_only}`",
                f"- continuous: `{continuous}`",
                f"- handledMessages: `{handled_messages}`",
                f"- latest user_openid: `{latest_openid}`",
                f"- latestUserPath: `{latest_user_path}`" if latest_user_path else "- latestUserPath: ``",
                f"- latestEventPath: `{latest_event_path}`" if latest_event_path else "- latestEventPath: ``",
            ]
        ),
    )
    return batch_dir


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        batch_dir = run_once(
            label=args.label,
            config_path=args.config,
            wait_seconds=args.wait_seconds,
            continuous=args.continuous,
            ready_only=args.ready_only,
            auto_reply=not args.no_auto_reply,
            reply_content=args.reply_content,
            reconnect_delay_seconds=args.reconnect_delay_seconds,
        )
    except RuntimeError as exc:
        print(f"[qq-gateway] {exc}", file=sys.stderr)
        return 1
    print(batch_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
