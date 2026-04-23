from __future__ import annotations

from pathlib import Path


WORKSPACE_MARKER = "ai_must_read.txt"


def resolve_project_root(project_dir: Path) -> Path:
    return Path(project_dir).resolve()


def resolve_workspace_root(project_dir: Path) -> Path:
    project_root = resolve_project_root(project_dir)
    for candidate in (project_root, *project_root.parents):
        if (candidate / WORKSPACE_MARKER).is_file():
            return candidate
    return project_root


def resolve_workspace_local_root(project_dir: Path) -> Path:
    return resolve_workspace_root(project_dir) / ".local"


def resolve_project_path(project_dir: Path, raw_path: str) -> Path:
    raw_path = raw_path.strip()
    if not raw_path:
        return Path()
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (resolve_project_root(project_dir) / path).resolve()


def resolve_workspace_path(project_dir: Path, raw_path: str) -> Path:
    raw_path = raw_path.strip()
    if not raw_path:
        return Path()
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (resolve_workspace_root(project_dir) / path).resolve()

