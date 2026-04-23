from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from env import require_env_value
from io_utils import read_json


DEFAULT_ACCESS_TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"
DEFAULT_API_BASE_URL = "https://api.sgroup.qq.com"
DEFAULT_TIMEOUT_MS = 10000
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY_SECONDS = 1.5
SUPPORTED_SCENES = {"group", "user"}
SUPPORTED_MEDIA_FILE_TYPES = {1, 2, 3, 4}


def load_qq_bot_message_config(project_dir: Path, config_path: Path | None = None) -> dict[str, Any]:
    resolved_path = config_path or (project_dir / "config" / "publish" / "qq_bot_message.json")
    payload = read_json(resolved_path)
    if not isinstance(payload, dict):
        raise RuntimeError("qq bot message config must be a JSON object.")
    return payload


def resolve_qq_bot_credentials(
    project_dir: Path,
    config: dict[str, Any],
    *,
    scene_override: str = "",
    target_openid_override: str = "",
) -> dict[str, Any]:
    app_id = require_env_value(project_dir, str(config.get("appIdEnvName", "QQ_BOT_APP_ID")))
    app_secret = require_env_value(project_dir, str(config.get("appSecretEnvName", "QQ_BOT_APP_SECRET")))

    scene = (scene_override or str(config.get("scene", ""))).strip().lower()
    if scene not in SUPPORTED_SCENES:
        raise RuntimeError(f"Unsupported QQ bot scene: {scene or '<empty>'}")

    target_openid = target_openid_override.strip()
    if not target_openid:
        if scene == "group":
            env_name = str(config.get("groupOpenIdEnvName", "QQ_BOT_GROUP_OPENID"))
        else:
            env_name = str(config.get("userOpenIdEnvName", "QQ_BOT_USER_OPENID"))
        target_openid = require_env_value(project_dir, env_name)

    return {
        "appId": app_id,
        "appSecret": app_secret,
        "scene": scene,
        "targetOpenId": target_openid,
        "accessTokenUrl": str(config.get("accessTokenUrl", DEFAULT_ACCESS_TOKEN_URL)),
        "apiBaseUrl": str(config.get("apiBaseUrl", DEFAULT_API_BASE_URL)).rstrip("/"),
        "timeoutMs": int(config.get("timeoutMs", DEFAULT_TIMEOUT_MS)),
    }


def build_message_endpoint(api_base_url: str, scene: str, target_openid: str) -> str:
    base_url = str(api_base_url or DEFAULT_API_BASE_URL).rstrip("/")
    scene_key = str(scene or "").strip().lower()
    target = str(target_openid or "").strip()
    if not target:
        raise RuntimeError("QQ bot target_openid is missing.")
    if scene_key == "group":
        return f"{base_url}/v2/groups/{target}/messages"
    if scene_key == "user":
        return f"{base_url}/v2/users/{target}/messages"
    raise RuntimeError(f"Unsupported QQ bot scene: {scene_key or '<empty>'}")


def build_file_endpoint(api_base_url: str, scene: str, target_openid: str) -> str:
    base_url = str(api_base_url or DEFAULT_API_BASE_URL).rstrip("/")
    scene_key = str(scene or "").strip().lower()
    target = str(target_openid or "").strip()
    if not target:
        raise RuntimeError("QQ bot target_openid is missing.")
    if scene_key == "group":
        return f"{base_url}/v2/groups/{target}/files"
    if scene_key == "user":
        return f"{base_url}/v2/users/{target}/files"
    raise RuntimeError(f"Unsupported QQ bot scene: {scene_key or '<empty>'}")


def build_text_message_payload(content: str) -> dict[str, Any]:
    text = str(content or "").strip()
    if not text:
        raise RuntimeError("QQ bot message content is empty.")
    return {
        "content": text,
        "msg_type": 0,
    }


def build_markdown_payload(content: str) -> dict[str, Any]:
    text = str(content or "").strip()
    if not text:
        raise RuntimeError("QQ bot markdown content is empty.")
    return {"content": text}


def build_media_payload(file_info: str) -> dict[str, Any]:
    resolved_file_info = str(file_info or "").strip()
    if not resolved_file_info:
        raise RuntimeError("QQ bot media file_info is empty.")
    return {"file_info": resolved_file_info}


def build_message_payload(
    *,
    msg_type: int,
    content: str = "",
    media: dict[str, Any] | None = None,
    msg_id: str = "",
    msg_seq: int = 0,
    event_id: str = "",
    is_wakeup: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"msg_type": int(msg_type)}
    text = str(content or "").strip()
    if text:
        payload["content"] = text
    if media is not None:
        payload["media"] = media
    if str(msg_id or "").strip():
        payload["msg_id"] = str(msg_id).strip()
    if int(msg_seq or 0) > 0:
        payload["msg_seq"] = int(msg_seq)
    if str(event_id or "").strip():
        payload["event_id"] = str(event_id).strip()
    if is_wakeup:
        payload["is_wakeup"] = True

    if payload["msg_type"] == 0 and "content" not in payload:
        raise RuntimeError("QQ bot text message content is empty.")
    if payload["msg_type"] == 7 and "media" not in payload:
        raise RuntimeError("QQ bot media message is missing media.file_info.")
    return payload


def build_rich_media_upload_payload(
    *,
    file_type: int,
    url: str = "",
    file_data: str = "",
    srv_send_msg: bool = False,
) -> dict[str, Any]:
    resolved_file_type = int(file_type)
    if resolved_file_type not in SUPPORTED_MEDIA_FILE_TYPES:
        raise RuntimeError(f"Unsupported QQ bot media file_type: {resolved_file_type}")
    resolved_url = str(url or "").strip()
    resolved_file_data = str(file_data or "").strip()
    if not resolved_url and not resolved_file_data:
        raise RuntimeError("QQ bot rich media upload requires url or file_data.")
    payload: dict[str, Any] = {
        "file_type": resolved_file_type,
        "srv_send_msg": bool(srv_send_msg),
    }
    if resolved_url:
        payload["url"] = resolved_url
    if resolved_file_data:
        payload["file_data"] = resolved_file_data
    return payload


def _sanitize_payload_for_log(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(payload)
    if "file_data" in sanitized:
        sanitized["file_data"] = f"<base64:{len(str(sanitized['file_data']))} chars>"
    return sanitized


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout_ms: int) -> dict[str, Any]:
    request = Request(
        str(url),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **headers,
        },
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
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"QQ bot response was not valid JSON: {raw}") from exc


def _resolve_auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"QQBot {str(access_token).strip()}"}


def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, (URLError, OSError)):
        return True
    if isinstance(exc, RuntimeError):
        lowered = str(exc).casefold()
        if "timed out" in lowered or "request failed" in lowered or "transport" in lowered:
            return True
        if "http 5" in lowered:
            return True
    return False


def _retry_call(fn, *, attempts: int = DEFAULT_RETRY_ATTEMPTS, base_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS):
    last_error: Exception | None = None
    for attempt in range(1, max(attempts, 1) + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= attempts or not _is_retryable_error(exc):
                break
            time.sleep(base_delay_seconds * attempt)
    assert last_error is not None
    raise last_error


def fetch_app_access_token(*, app_id: str, app_secret: str, access_token_url: str, timeout_ms: int) -> dict[str, Any]:
    payload = {
        "appId": app_id,
        "clientSecret": app_secret,
    }
    result = _retry_call(lambda: _post_json(access_token_url, payload, {}, timeout_ms))
    if not str(result.get("access_token", "")).strip():
        raise RuntimeError(f"QQ bot access token response missing access_token: {result}")
    result.setdefault("_request", {"url": access_token_url, "payload": payload})
    return result


def send_message(
    *,
    access_token: str,
    api_base_url: str,
    scene: str,
    target_openid: str,
    payload: dict[str, Any],
    timeout_ms: int,
) -> dict[str, Any]:
    endpoint = build_message_endpoint(api_base_url, scene, target_openid)
    result = _post_json(
        endpoint,
        payload,
        _resolve_auth_headers(access_token),
        timeout_ms,
    )
    result.setdefault("_request", {"url": endpoint, "payload": payload})
    return result


def send_text_message(
    *,
    access_token: str,
    api_base_url: str,
    scene: str,
    target_openid: str,
    content: str,
    timeout_ms: int,
    msg_id: str = "",
    msg_seq: int = 0,
    event_id: str = "",
    is_wakeup: bool = False,
) -> dict[str, Any]:
    payload = build_message_payload(
        msg_type=0,
        content=content,
        msg_id=msg_id,
        msg_seq=msg_seq,
        event_id=event_id,
        is_wakeup=is_wakeup,
    )
    return send_message(
        access_token=access_token,
        api_base_url=api_base_url,
        scene=scene,
        target_openid=target_openid,
        payload=payload,
        timeout_ms=timeout_ms,
    )


def send_markdown_message(
    *,
    access_token: str,
    api_base_url: str,
    scene: str,
    target_openid: str,
    markdown_content: str,
    timeout_ms: int,
    msg_id: str = "",
    msg_seq: int = 0,
    event_id: str = "",
    is_wakeup: bool = False,
) -> dict[str, Any]:
    payload = build_message_payload(
        msg_type=2,
        msg_id=msg_id,
        msg_seq=msg_seq,
        event_id=event_id,
        is_wakeup=is_wakeup,
    )
    payload["markdown"] = build_markdown_payload(markdown_content)
    return send_message(
        access_token=access_token,
        api_base_url=api_base_url,
        scene=scene,
        target_openid=target_openid,
        payload=payload,
        timeout_ms=timeout_ms,
    )


def upload_rich_media(
    *,
    access_token: str,
    api_base_url: str,
    scene: str,
    target_openid: str,
    file_type: int,
    timeout_ms: int,
    url: str = "",
    file_data: str = "",
    srv_send_msg: bool = False,
) -> dict[str, Any]:
    endpoint = build_file_endpoint(api_base_url, scene, target_openid)
    payload = build_rich_media_upload_payload(
        file_type=file_type,
        url=url,
        file_data=file_data,
        srv_send_msg=srv_send_msg,
    )
    result = _retry_call(
        lambda: _post_json(
            endpoint,
            payload,
            _resolve_auth_headers(access_token),
            timeout_ms,
        )
    )
    result.setdefault("_request", {"url": endpoint, "payload": _sanitize_payload_for_log(payload)})
    return result


def send_media_message(
    *,
    access_token: str,
    api_base_url: str,
    scene: str,
    target_openid: str,
    file_info: str,
    timeout_ms: int,
    content: str = "",
    msg_id: str = "",
    msg_seq: int = 0,
    event_id: str = "",
    is_wakeup: bool = False,
) -> dict[str, Any]:
    payload = build_message_payload(
        msg_type=7,
        content=content,
        media=build_media_payload(file_info),
        msg_id=msg_id,
        msg_seq=msg_seq,
        event_id=event_id,
        is_wakeup=is_wakeup,
    )
    return send_message(
        access_token=access_token,
        api_base_url=api_base_url,
        scene=scene,
        target_openid=target_openid,
        payload=payload,
        timeout_ms=timeout_ms,
    )


def _read_file_as_base64(path: Path) -> str:
    resolved_path = path.resolve()
    if not resolved_path.exists():
        raise RuntimeError(f"QQ bot media file does not exist: {resolved_path}")
    return base64.b64encode(resolved_path.read_bytes()).decode("ascii")


def detect_image_file_type(image_path: Path) -> int:
    suffix = image_path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg"}:
        return 1
    raise RuntimeError(f"Unsupported QQ bot image format: {suffix or '<empty>'}")


def send_local_image_message(
    *,
    access_token: str,
    api_base_url: str,
    scene: str,
    target_openid: str,
    image_path: Path,
    timeout_ms: int,
    content: str = "",
    msg_id: str = "",
    msg_seq: int = 0,
    event_id: str = "",
    is_wakeup: bool = False,
) -> dict[str, Any]:
    resolved_image_path = Path(image_path).resolve()
    upload_result = upload_rich_media(
        access_token=access_token,
        api_base_url=api_base_url,
        scene=scene,
        target_openid=target_openid,
        file_type=detect_image_file_type(resolved_image_path),
        file_data=_read_file_as_base64(resolved_image_path),
        srv_send_msg=False,
        timeout_ms=timeout_ms,
    )
    file_info = str(upload_result.get("file_info", "")).strip()
    if not file_info:
        raise RuntimeError(f"QQ bot rich media upload missing file_info: {upload_result}")
    message_result = send_media_message(
        access_token=access_token,
        api_base_url=api_base_url,
        scene=scene,
        target_openid=target_openid,
        file_info=file_info,
        content=content,
        msg_id=msg_id,
        msg_seq=msg_seq,
        event_id=event_id,
        is_wakeup=is_wakeup,
        timeout_ms=timeout_ms,
    )
    message_result.setdefault(
        "_upload",
        {
            "url": upload_result.get("_request", {}).get("url", ""),
            "payload": upload_result.get("_request", {}).get("payload", {}),
            "fileUuid": upload_result.get("file_uuid", ""),
            "ttl": upload_result.get("ttl"),
        },
    )
    return message_result

