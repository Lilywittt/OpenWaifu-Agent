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
    stage_entries = list_stage_profile_entries(project_dir)
    return {stage_key: entry["profile"] for stage_key, entry in stage_entries.items()}


def list_stage_profile_entries(project_dir: Path) -> dict[str, dict[str, Any]]:
    stages = _load_config(project_dir).get("stages")
    if not isinstance(stages, dict) or not stages:
        raise RuntimeError(f"{CONFIG_PATH.as_posix()} must define non-empty stages.")
    normalized_stages: dict[str, dict[str, Any]] = {}
    for stage_key, stage_entry in stages.items():
        normalized_stage_key = str(stage_key or "").strip()
        if not normalized_stage_key:
            raise RuntimeError(f"{CONFIG_PATH.as_posix()} contains an empty stage key.")
        normalized_stages[normalized_stage_key] = _normalize_stage_profile_entry(
            normalized_stage_key,
            stage_entry,
        )
    return normalized_stages


def _normalize_stage_profile_entry(stage_key: str, stage_entry: Any) -> dict[str, Any]:
    if isinstance(stage_entry, str):
        normalized_profile_name = str(stage_entry or "").strip()
        if not normalized_profile_name:
            raise RuntimeError(f"{CONFIG_PATH.as_posix()} stage {stage_key!r} is missing a profile.")
        return {"profile": normalized_profile_name}
    if not isinstance(stage_entry, dict):
        raise RuntimeError(f"{CONFIG_PATH.as_posix()} stage {stage_key!r} must be a string or JSON object.")
    normalized_profile_name = str(stage_entry.get("profile", "") or "").strip()
    if not normalized_profile_name:
        raise RuntimeError(f"{CONFIG_PATH.as_posix()} stage {stage_key!r} is missing a profile.")
    normalized_entry = {"profile": normalized_profile_name}
    for key, value in stage_entry.items():
        normalized_key = str(key or "").strip()
        if not normalized_key or normalized_key == "profile":
            continue
        normalized_entry[normalized_key] = copy.deepcopy(value)
    return normalized_entry


def resolve_stage_model_profile(project_dir: Path, stage_key: str) -> dict[str, Any]:
    normalized_stage_key = str(stage_key or "").strip()
    if not normalized_stage_key:
        raise RuntimeError("stage key cannot be empty.")

    stages = list_stage_profile_entries(project_dir)
    stage_entry = stages.get(normalized_stage_key)
    profile_name = str((stage_entry or {}).get("profile", "")).strip()
    if not profile_name:
        raise RuntimeError(f"llm stage is not configured: {normalized_stage_key}")

    profiles = list_model_profiles(project_dir)
    profile = profiles.get(profile_name)
    if profile is None:
        raise RuntimeError(
            f"{CONFIG_PATH.as_posix()} stage {normalized_stage_key!r} references unknown profile {profile_name!r}."
        )
    return copy.deepcopy(profile)


def resolve_stage_llm_config(project_dir: Path, stage_key: str) -> dict[str, Any]:
    profile = resolve_stage_model_profile(project_dir, stage_key)
    stage_entry = list_stage_profile_entries(project_dir)[str(stage_key or "").strip()]
    merged = copy.deepcopy(profile)
    for key, value in stage_entry.items():
        if key == "profile":
            continue
        merged[key] = copy.deepcopy(value)
    return merged
