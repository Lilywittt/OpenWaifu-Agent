from __future__ import annotations

from pathlib import Path
from typing import Any

from .io_utils import read_json
from .paths import resolve_project_path
from .character_catalog import active_character_id


def load_app_config(project_dir: Path) -> dict[str, Any]:
    payload = read_json(project_dir / "config" / "app.json")
    if not isinstance(payload, dict):
        raise RuntimeError("config/app.json must be a JSON object.")
    return payload


def load_model_profiles(project_dir: Path) -> dict[str, Any]:
    payload = read_json(project_dir / "config" / "model_profiles.json")
    if not isinstance(payload, dict) or not isinstance(payload.get("profiles"), dict):
        raise RuntimeError("config/model_profiles.json must contain profiles.")
    return payload


def resolve_active_model_profile(project_dir: Path) -> dict[str, Any]:
    app_config = load_app_config(project_dir)
    profile_id = str(app_config.get("activeModelProfile", "")).strip()
    profiles = load_model_profiles(project_dir)["profiles"]
    if profile_id not in profiles:
        raise RuntimeError(f"active model profile does not exist: {profile_id}")
    profile = dict(profiles[profile_id])
    profile["id"] = profile_id
    return profile


def resolve_character_path(project_dir: Path, character_id: str | None = None) -> Path:
    app_config = load_app_config(project_dir)
    resolved_id = str(character_id or active_character_id(project_dir) or app_config.get("defaultCharacterId", "default")).strip() or "default"
    return resolve_project_path(project_dir, Path("characters") / f"{resolved_id}.json")


def load_command_config(project_dir: Path) -> dict[str, list[str]]:
    payload = read_json(project_dir / "config" / "bot_commands.json")
    if not isinstance(payload, dict):
        raise RuntimeError("config/bot_commands.json must be a JSON object.")
    commands: dict[str, list[str]] = {}
    for key, value in payload.items():
        if isinstance(value, list):
            commands[str(key)] = [str(item).strip() for item in value if str(item).strip()]
        else:
            commands[str(key)] = [str(value).strip()] if str(value).strip() else []
    return commands
