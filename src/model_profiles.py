from __future__ import annotations

from pathlib import Path

from io_utils import read_json


CONFIG_PATH = Path("config") / "llm_profiles.json"


def _resolve_configured_path(project_dir: Path, config: dict, key: str) -> Path:
    raw_path = str(config.get(key, "")).strip()
    if not raw_path:
        raise RuntimeError(f"{CONFIG_PATH.as_posix()} is missing {key}.")

    resolved_path = Path(raw_path)
    if not resolved_path.is_absolute():
        resolved_path = (project_dir / resolved_path).resolve()

    if not resolved_path.is_file():
        raise RuntimeError(f"configured model config does not exist: {resolved_path}")
    return resolved_path


def _load_config(project_dir: Path) -> dict:
    config_path = project_dir / CONFIG_PATH
    if not config_path.is_file():
        raise RuntimeError(f"llm profiles config does not exist: {config_path}")
    return read_json(config_path)


def resolve_creative_model_config_path(project_dir: Path) -> Path:
    config = _load_config(project_dir)
    return _resolve_configured_path(project_dir, config, "creativeModelConfigPath")


def resolve_prompt_guard_model_config_path(project_dir: Path) -> Path:
    config = _load_config(project_dir)
    return _resolve_configured_path(project_dir, config, "promptGuardModelConfigPath")
