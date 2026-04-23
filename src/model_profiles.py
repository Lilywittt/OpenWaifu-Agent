from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from io_utils import read_json


CONFIG_PATH = Path("config") / "llm_profiles.json"


def _load_config(project_dir: Path) -> dict[str, Any]:
    config_path = project_dir / CONFIG_PATH
    if not config_path.is_file():
        raise RuntimeError(f"llm profiles config does not exist: {config_path}")
    config = read_json(config_path)
    if not isinstance(config, dict):
        raise RuntimeError(f"{CONFIG_PATH.as_posix()} must be a JSON object.")
    return config


def list_model_profiles(project_dir: Path) -> dict[str, dict[str, Any]]:
    profiles = _load_config(project_dir).get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise RuntimeError(f"{CONFIG_PATH.as_posix()} must define non-empty profiles.")
    normalized_profiles: dict[str, dict[str, Any]] = {}
    for profile_name, profile in profiles.items():
        if not isinstance(profile_name, str) or not profile_name.strip():
            raise RuntimeError(f"{CONFIG_PATH.as_posix()} contains an empty profile name.")
        if not isinstance(profile, dict):
            raise RuntimeError(f"profile {profile_name!r} must be a JSON object.")
        normalized_profiles[profile_name.strip()] = copy.deepcopy(profile)
    return normalized_profiles


def list_stage_profile_map(project_dir: Path) -> dict[str, str]:
    stages = _load_config(project_dir).get("stages")
    if not isinstance(stages, dict) or not stages:
        raise RuntimeError(f"{CONFIG_PATH.as_posix()} must define non-empty stages.")
    normalized_stages: dict[str, str] = {}
    for stage_key, profile_name in stages.items():
        normalized_stage_key = str(stage_key or "").strip()
        normalized_profile_name = str(profile_name or "").strip()
        if not normalized_stage_key:
            raise RuntimeError(f"{CONFIG_PATH.as_posix()} contains an empty stage key.")
        if not normalized_profile_name:
            raise RuntimeError(f"{CONFIG_PATH.as_posix()} stage {normalized_stage_key!r} is missing a profile.")
        normalized_stages[normalized_stage_key] = normalized_profile_name
    return normalized_stages


def resolve_stage_model_profile(project_dir: Path, stage_key: str) -> dict[str, Any]:
    normalized_stage_key = str(stage_key or "").strip()
    if not normalized_stage_key:
        raise RuntimeError("stage key cannot be empty.")

    stages = list_stage_profile_map(project_dir)
    profile_name = stages.get(normalized_stage_key)
    if not profile_name:
        raise RuntimeError(f"llm stage is not configured: {normalized_stage_key}")

    profiles = list_model_profiles(project_dir)
    profile = profiles.get(profile_name)
    if profile is None:
        raise RuntimeError(
            f"{CONFIG_PATH.as_posix()} stage {normalized_stage_key!r} references unknown profile {profile_name!r}."
        )
    return copy.deepcopy(profile)
