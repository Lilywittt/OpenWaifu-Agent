from __future__ import annotations

from pathlib import Path


def parse_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_project_env(project_dir: Path) -> dict[str, str]:
    return parse_env(project_dir / ".env")


def get_env_value(project_dir: Path, env_name: str, default: str = "") -> str:
    env_map = load_project_env(project_dir)
    value = env_map.get(str(env_name or "").strip(), "")
    return value if value else default


def require_env_value(project_dir: Path, env_name: str) -> str:
    value = get_env_value(project_dir, env_name, "")
    if not value:
        raise RuntimeError(f"{env_name} is missing.")
    return value
