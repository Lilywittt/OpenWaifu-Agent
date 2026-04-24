from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from publish.qq_bot_client import (
    fetch_app_access_token,
    load_qq_bot_message_config,
    resolve_qq_bot_credentials,
    send_local_image_message,
)


def send_workbench_report_to_qq(
    *,
    project_dir: Path,
    target_config: dict[str, Any],
    report_package: dict[str, Any],
) -> dict[str, Any]:
    config_path_raw = str(target_config.get("configPath", "config/publish/qq_bot_message.json")).strip()
    config_path = Path(config_path_raw)
    if not config_path.is_absolute():
        config_path = (project_dir / config_path).resolve()
    config = dict(load_qq_bot_message_config(project_dir, config_path))
    for key in (
        "appIdEnvName",
        "appSecretEnvName",
        "groupOpenIdEnvName",
        "userOpenIdEnvName",
        "accessTokenUrl",
        "apiBaseUrl",
        "timeoutMs",
    ):
        if key in target_config:
            config[key] = target_config[key]

    credentials = resolve_qq_bot_credentials(
        project_dir,
        config,
        scene_override=str(target_config.get("scene", "")).strip(),
        target_openid_override=str(target_config.get("targetOpenId", "")).strip(),
    )
    token_response = fetch_app_access_token(
        app_id=credentials["appId"],
        app_secret=credentials["appSecret"],
        access_token_url=credentials["accessTokenUrl"],
        timeout_ms=credentials["timeoutMs"],
    )
    image_path = Path(str(report_package["imagePath"])).resolve()
    message_response = send_local_image_message(
        access_token=str(token_response["access_token"]),
        api_base_url=credentials["apiBaseUrl"],
        scene=credentials["scene"],
        target_openid=credentials["targetOpenId"],
        image_path=image_path,
        content=str(report_package["socialPostText"]).strip(),
        timeout_ms=credentials["timeoutMs"],
    )
    return {
        "adapter": "qq_report",
        "status": "sent",
        "sentAt": datetime.now().isoformat(timespec="seconds"),
        "runId": str(report_package["runId"]),
        "scene": credentials["scene"],
        "targetOpenId": credentials["targetOpenId"],
        "messageId": str(message_response.get("id", "")).strip(),
        "timestamp": message_response.get("timestamp", ""),
        "imagePath": str(image_path),
        "contentPreview": str(report_package["socialPostText"]).strip()[:80],
        "upload": message_response.get("_upload", {}),
    }

