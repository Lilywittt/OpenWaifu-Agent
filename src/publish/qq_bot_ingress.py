from __future__ import annotations

import json
import time
import threading

import websocket
from websocket._exceptions import WebSocketTimeoutException

from .qq_bot_client import fetch_app_access_token
from .qq_bot_gateway import (
    QQ_BOT_C2C_SERVICE_INTENTS,
    build_gateway_heartbeat_payload,
    build_gateway_identify_payload,
    fetch_gateway_info,
)


def recv_gateway_payload(ws: websocket.WebSocket, *, timeout_seconds: float) -> tuple[str | None, dict | None]:
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


def connect_gateway(credentials: dict, token_response: dict) -> tuple[websocket.WebSocket, dict]:
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


def fetch_access_token(credentials: dict) -> dict:
    return fetch_app_access_token(
        app_id=credentials["appId"],
        app_secret=credentials["appSecret"],
        access_token_url=credentials["accessTokenUrl"],
        timeout_ms=credentials["timeoutMs"],
    )
