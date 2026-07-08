from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..io_utils import ensure_dir, write_json
from .client import fetch_app_access_token


QQ_BOT_C2C_INTENT = 1 << 25
QQ_BOT_INTERACTION_INTENT = 1 << 26
QQ_BOT_C2C_SERVICE_INTENTS = QQ_BOT_C2C_INTENT | QQ_BOT_INTERACTION_INTENT


def gateway_state_root(project_dir: Path) -> Path:
    return ensure_dir(project_dir / "runtime" / "qq_gateway")


def gateway_events_root(project_dir: Path) -> Path:
    return ensure_dir(gateway_state_root(project_dir) / "events")


def build_gateway_info_url(api_base_url: str) -> str:
    return f"{str(api_base_url).rstrip('/')}/gateway/bot"


def build_gateway_identify_payload(*, access_token: str, intents: int, shard_id: int = 0, shard_count: int = 1) -> dict[str, Any]:
    return {
        "op": 2,
        "d": {
            "token": f"QQBot {str(access_token).strip()}",
            "intents": int(intents),
            "shard": [int(shard_id), int(shard_count)],
            "properties": {
                "$os": "windows",
                "$browser": "openwaifu-roleplay-agent",
                "$device": "openwaifu-roleplay-agent",
            },
        },
    }


def build_gateway_heartbeat_payload(seq: int | None) -> dict[str, Any]:
    return {"op": 1, "d": seq}


def fetch_gateway_info(credentials: dict[str, Any], token_response: dict[str, Any]) -> dict[str, Any]:
    request = Request(
        build_gateway_info_url(str(credentials["apiBaseUrl"])),
        headers={
            "Authorization": f"QQBot {str(token_response['access_token']).strip()}",
            "X-Union-Appid": str(credentials["appId"]).strip(),
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=max(int(credentials["timeoutMs"]), 1000) / 1000.0) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"QQ bot gateway HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"QQ bot gateway request failed: {exc}") from exc
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not str(payload.get("url", "")).strip():
        raise RuntimeError(f"QQ bot gateway info response missing url: {payload}")
    return payload


def connect_gateway(credentials: dict[str, Any]):
    try:
        import websocket
        from websocket._exceptions import WebSocketTimeoutException
    except ImportError as exc:
        raise RuntimeError("websocket-client is required. Install with: pip install websocket-client") from exc

    token_response = fetch_app_access_token(credentials)
    gateway_info = fetch_gateway_info(credentials, token_response)
    ws = websocket.create_connection(
        str(gateway_info["url"]),
        timeout=max(int(credentials["timeoutMs"]), 1000) / 1000.0,
    )
    hello_payload = json.loads(ws.recv())
    heartbeat_interval = int(hello_payload.get("d", {}).get("heartbeat_interval", 0))
    if heartbeat_interval <= 0:
        ws.close()
        raise RuntimeError(f"QQ bot gateway hello payload missing heartbeat interval: {hello_payload}")
    state = {"seq": None, "running": True}

    def heartbeat_loop() -> None:
        while state["running"]:
            time.sleep(heartbeat_interval / 1000.0)
            if not state["running"]:
                return
            try:
                ws.send(json.dumps(build_gateway_heartbeat_payload(state["seq"]), ensure_ascii=False))
            except Exception:
                return

    threading.Thread(target=heartbeat_loop, daemon=True).start()
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
        "timeoutException": WebSocketTimeoutException,
    }


def recv_gateway_payload(ws, *, timeout_seconds: float, timeout_exception: type[Exception]) -> tuple[str | None, dict[str, Any] | None]:
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
            except timeout_exception:
                return None, None
            text = str(raw_message or "").strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return text, payload
    finally:
        ws.settimeout(previous_timeout)


def save_gateway_status(project_dir: Path, *, gateway_url: str, session_id: str = "", event_type: str = "") -> None:
    write_json(
        gateway_state_root(project_dir) / "latest_status.json",
        {
            "updatedAt": datetime.now().isoformat(timespec="seconds"),
            "gatewayUrl": gateway_url,
            "sessionId": session_id,
            "lastEventType": event_type,
        },
    )


def save_gateway_event(project_dir: Path, *, payload: dict[str, Any], raw_message: str) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    payload_id = str(payload.get("id", "")).strip() or stamp
    safe_id = payload_id.replace("/", "_").replace("\\", "_").replace(":", "_")
    event_path = gateway_events_root(project_dir) / f"{stamp}_{safe_id}.json"
    write_json(
        event_path,
        {
            "receivedAt": datetime.now().isoformat(timespec="seconds"),
            "rawMessage": raw_message,
            "payload": payload,
        },
    )
    return event_path
