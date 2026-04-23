from __future__ import annotations

from pathlib import Path
from typing import Any

from env import get_env_value
from io_utils import normalize_spaces


def _qq_bot_config_path(project_dir: Path) -> Path:
    return Path(project_dir).resolve() / "config" / "publish" / "qq_bot_message.json"


def _safe_read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def read_bot_display_identity(project_dir: Path, *, title_suffix: str) -> dict[str, str]:
    project_dir = Path(project_dir).resolve()
    config_payload = _safe_read_json(_qq_bot_config_path(project_dir)) or {}
    env_name = normalize_spaces(str(config_payload.get("botDisplayNameEnvName", ""))) or "QQ_BOT_DISPLAY_NAME"
    env_display_name = normalize_spaces(get_env_value(project_dir, env_name, ""))
    config_display_name = normalize_spaces(str(config_payload.get("botDisplayName", "")))
    project_name = project_dir.name
    bot_display_name = env_display_name or config_display_name
    title = (
        f"{bot_display_name} {title_suffix}".strip()
        if bot_display_name
        else f"{project_name} {title_suffix}".strip()
    )
    return {
        "projectName": project_name,
        "botDisplayName": bot_display_name,
        "title": title,
    }
