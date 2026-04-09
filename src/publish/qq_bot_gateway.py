from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from io_utils import ensure_dir, write_json

from .qq_bot_identity import extract_user_openid
from .qq_bot_identity import persist_user_openid as persist_user_openid_to_state
from .state import publish_state_root


QQ_BOT_C2C_INTENT = 1 << 25
QQ_BOT_INTERACTION_INTENT = 1 << 26
QQ_BOT_C2C_SERVICE_INTENTS = QQ_BOT_C2C_INTENT | QQ_BOT_INTERACTION_INTENT


def qq_bot_gateway_state_root(project_dir: Path) -> Path:
    return ensure_dir(publish_state_root(project_dir) / "qq_bot_gateway")


def qq_bot_gateway_events_root(project_dir: Path) -> Path:
    return ensure_dir(qq_bot_gateway_state_root(project_dir) / "events")


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
                "$browser": "codex",
                "$device": "codex",
            },
        },
    }


def build_gateway_heartbeat_payload(seq: int | None) -> dict[str, Any]:
    return {
        "op": 1,
        "d": seq,
    }


def _request_json(url: str, *, headers: dict[str, str], timeout_ms: int) -> dict[str, Any]:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=max(timeout_ms, 1000) / 1000.0) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"QQ bot gateway HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"QQ bot gateway request failed: {exc}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"QQ bot gateway response was not valid JSON: {raw}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"QQ bot gateway response must be a JSON object: {payload}")
    return payload


def fetch_gateway_info(*, app_id: str, access_token: str, api_base_url: str, timeout_ms: int) -> dict[str, Any]:
    payload = _request_json(
        build_gateway_info_url(api_base_url),
        headers={
            "Authorization": f"QQBot {str(access_token).strip()}",
            "X-Union-Appid": str(app_id).strip(),
        },
        timeout_ms=timeout_ms,
    )
    if not str(payload.get("url", "")).strip():
        raise RuntimeError(f"QQ bot gateway info response missing url: {payload}")
    return payload


def save_gateway_event(project_dir: Path, *, payload: dict[str, Any], raw_message: str) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    payload_id = str(payload.get("id", "")).strip() or stamp
    safe_id = payload_id.replace("/", "_").replace("\\", "_").replace(":", "_")
    event_path = qq_bot_gateway_events_root(project_dir) / f"{stamp}_{safe_id}.json"
    write_json(
        event_path,
        {
            "receivedAt": datetime.now().isoformat(timespec="seconds"),
            "rawMessage": raw_message,
            "payload": payload,
        },
    )
    return event_path


def persist_user_openid(project_dir: Path, *, user_openid: str, event_path: Path) -> Path:
    return persist_user_openid_to_state(
        project_dir,
        state_root=qq_bot_gateway_state_root(project_dir),
        user_openid=user_openid,
        event_path=event_path,
    )


def save_gateway_status(project_dir: Path, *, gateway_url: str, session_id: str = "", event_type: str = "") -> Path:
    status_path = qq_bot_gateway_state_root(project_dir) / "latest_status.json"
    write_json(
        status_path,
        {
            "updatedAt": datetime.now().isoformat(timespec="seconds"),
            "gatewayUrl": gateway_url,
            "sessionId": session_id,
            "lastEventType": event_type,
        },
    )
    return status_path
