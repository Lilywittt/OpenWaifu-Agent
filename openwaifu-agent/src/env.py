from __future__ import annotations

from pathlib import Path

from path_policy import (
    resolve_project_path,
    resolve_workspace_path as _resolve_workspace_path,
    resolve_workspace_root as _resolve_workspace_root,
)

def resolve_workspace_root(project_dir: Path) -> Path:
    return _resolve_workspace_root(project_dir)


def parse_project_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#") or "=" not in trimmed:
            continue
        key, raw = trimmed.split("=", 1)
        values[key.strip()] = raw.strip().strip('"')
    return values


def load_project_env(project_dir: Path) -> dict[str, str]:
    return parse_project_env(project_dir / ".env")


def get_env_value(project_dir: Path, env_name: str, default: str = "") -> str:
    env_map = load_project_env(project_dir)
    if env_name in env_map and env_map[env_name] != "":
        return env_map[env_name]
    return default


def require_env_value(project_dir: Path, env_name: str) -> str:
    value = get_env_value(project_dir, env_name, "")
    if not value:
        raise RuntimeError(f"{env_name} is missing.")
    return value


def resolve_env_path(project_dir: Path, env_name: str, default: str = "") -> Path:
    raw = get_env_value(project_dir, env_name, default).strip()
    if not raw:
        return Path()
    return resolve_project_path(project_dir, raw)


def resolve_workspace_path(project_dir: Path, raw_path: str) -> Path:
    return _resolve_workspace_path(project_dir, raw_path)
