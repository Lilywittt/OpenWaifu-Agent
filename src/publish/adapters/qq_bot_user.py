from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..qq_bot_client import (
    fetch_app_access_token,
    load_qq_bot_message_config,
    resolve_qq_bot_credentials,
    send_local_image_message,
)


def _resolve_qq_bot_target_config(project_dir: Path, target_config: dict) -> dict:
    config_path_raw = str(target_config.get("configPath", "config/publish/qq_bot_message.json")).strip()
    config_path = Path(config_path_raw)
    if not config_path.is_absolute():
        config_path = (project_dir / config_path).resolve()
    config = dict(load_qq_bot_message_config(project_dir, config_path))
    for key in ("appIdEnvName", "appSecretEnvName", "groupOpenIdEnvName", "userOpenIdEnvName", "accessTokenUrl", "apiBaseUrl", "timeoutMs"):
        if key in target_config:
            config[key] = target_config[key]
    return config


def publish_to_qq_bot_user(
    *,
    project_dir: Path,
    bundle,
    target_id: str,
    target_config: dict,
    publish_input: dict,
) -> dict:
    config = _resolve_qq_bot_target_config(project_dir, target_config)
    credentials = resolve_qq_bot_credentials(
        project_dir,
        config,
        scene_override=str(target_config.get("scene", "user")).strip() or "user",
        target_openid_override=str(target_config.get("targetOpenId", "")).strip(),
    )
    if credentials["scene"] != "user":
        raise RuntimeError(f"qq_bot_user adapter only supports scene=user, got: {credentials['scene']}")

    token_response = fetch_app_access_token(
        app_id=credentials["appId"],
        app_secret=credentials["appSecret"],
        access_token_url=credentials["accessTokenUrl"],
        timeout_ms=credentials["timeoutMs"],
    )
    image_path = Path(str(publish_input.get("imagePath", "")).strip()).resolve()
    if not image_path.exists():
        raise RuntimeError(f"publish input image path does not exist: {image_path}")

    social_post_text = str(publish_input.get("socialPostText", "")).strip()
    reply_message_id = str(target_config.get("replyMessageId", "")).strip()
    reply_message_seq = int(target_config.get("replyMessageSeq", 0) or 0)
    reply_event_id = str(target_config.get("replyEventId", "")).strip()
    message_response = send_local_image_message(
        access_token=str(token_response["access_token"]),
        api_base_url=credentials["apiBaseUrl"],
        scene="user",
        target_openid=credentials["targetOpenId"],
        image_path=image_path,
        content=social_post_text,
        timeout_ms=credentials["timeoutMs"],
        msg_id=reply_message_id,
        msg_seq=reply_message_seq,
        event_id=reply_event_id,
    )

    return {
        "targetId": target_id,
        "adapter": "qq_bot_user",
        "status": "published",
        "publishedAt": datetime.now().isoformat(timespec="seconds"),
        "scene": "user",
        "targetOpenId": credentials["targetOpenId"],
        "messageId": str(message_response.get("id", "")).strip(),
        "timestamp": message_response.get("timestamp", ""),
        "contentPreview": social_post_text[:80],
        "imagePath": str(image_path),
        "replyMode": "passive" if reply_message_id or reply_event_id else "proactive",
        "upload": message_response.get("_upload", {}),
        "postUrl": f"qqbot://user/{credentials['targetOpenId']}/{str(message_response.get('id', '')).strip()}",
    }
