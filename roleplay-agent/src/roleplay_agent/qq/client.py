from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..env import require_env_value
from ..io_utils import read_json


DEFAULT_ACCESS_TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"
DEFAULT_API_BASE_URL = "https://api.sgroup.qq.com"
DEFAULT_TIMEOUT_MS = 10000

TOKEN_CACHE: dict[str, dict[str, Any]] = {}
TOKEN_CACHE_LOCK = threading.Lock()


def load_qq_config(project_dir: Path, config_path: Path | None = None) -> dict[str, Any]:
    resolved = config_path or (project_dir / "config" / "qq_bot.json")
    payload = read_json(resolved)
    if not isinstance(payload, dict):
        raise RuntimeError("QQ bot config must be a JSON object.")
    return payload


def resolve_qq_credentials(project_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    return {
        "appId": require_env_value(project_dir, str(config.get("appIdEnvName", "QQ_BOT_APP_ID"))),
        "appSecret": require_env_value(project_dir, str(config.get("appSecretEnvName", "QQ_BOT_APP_SECRET"))),
        "accessTokenUrl": str(config.get("accessTokenUrl", DEFAULT_ACCESS_TOKEN_URL)),
        "apiBaseUrl": str(config.get("apiBaseUrl", DEFAULT_API_BASE_URL)).rstrip("/"),
        "timeoutMs": int(config.get("timeoutMs", DEFAULT_TIMEOUT_MS)),
    }


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout_ms: int) -> dict[str, Any]:
    request = Request(
        str(url),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urlopen(request, timeout=max(timeout_ms, 1000) / 1000.0) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"QQ bot HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"QQ bot request failed: {exc}") from exc
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"QQ bot response was not valid JSON: {raw}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"QQ bot response must be an object: {payload}")
    return payload


def fetch_app_access_token(credentials: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "appId": credentials["appId"],
        "clientSecret": credentials["appSecret"],
    }
    result = _post_json(str(credentials["accessTokenUrl"]), payload, {}, int(credentials["timeoutMs"]))
    if not str(result.get("access_token", "")).strip():
        raise RuntimeError(f"QQ bot access token response missing access_token: {result}")
    return result


def resolve_cached_access_token(credentials: dict[str, Any]) -> str:
    app_id = str(credentials.get("appId", "")).strip()
    cache_key = f"{app_id}:{credentials.get('accessTokenUrl', '')}"
    now = time.time()
    with TOKEN_CACHE_LOCK:
        cached = TOKEN_CACHE.get(cache_key)
        if cached and float(cached.get("expiresAt", 0)) > now:
            return str(cached.get("accessToken", "")).strip()
    token_response = fetch_app_access_token(credentials)
    access_token = str(token_response["access_token"]).strip()
    expires_in = int(token_response.get("expires_in", 0) or 0)
    ttl_seconds = max(expires_in - 60, 60) if expires_in > 0 else 300
    with TOKEN_CACHE_LOCK:
        TOKEN_CACHE[cache_key] = {"accessToken": access_token, "expiresAt": now + ttl_seconds}
    return access_token


def build_user_message_endpoint(api_base_url: str, user_openid: str) -> str:
    target = str(user_openid or "").strip()
    if not target:
        raise RuntimeError("QQ bot user_openid is missing.")
    return f"{str(api_base_url).rstrip('/')}/v2/users/{target}/messages"


def build_text_message_payload(
    *,
    content: str,
    msg_id: str = "",
    msg_seq: int = 0,
    event_id: str = "",
) -> dict[str, Any]:
    text = str(content or "").strip()
    if not text:
        raise RuntimeError("QQ bot message content is empty.")
    payload: dict[str, Any] = {"msg_type": 0, "content": text}
    if str(msg_id or "").strip():
        payload["msg_id"] = str(msg_id).strip()
    if int(msg_seq or 0) > 0:
        payload["msg_seq"] = int(msg_seq)
    if str(event_id or "").strip():
        payload["event_id"] = str(event_id).strip()
    return payload


def send_text_message(
    *,
    credentials: dict[str, Any],
    user_openid: str,
    content: str,
    msg_id: str = "",
    msg_seq: int = 0,
    event_id: str = "",
) -> dict[str, Any]:
    access_token = resolve_cached_access_token(credentials)
    endpoint = build_user_message_endpoint(str(credentials["apiBaseUrl"]), user_openid)
    payload = build_text_message_payload(content=content, msg_id=msg_id, msg_seq=msg_seq, event_id=event_id)
    return _post_json(
        endpoint,
        payload,
        {"Authorization": f"QQBot {access_token}"},
        int(credentials["timeoutMs"]),
    )
