from __future__ import annotations

from pathlib import Path
from typing import Any

from .io_utils import read_json
from .paths import resolve_project_path


def load_user_persona(project_dir: Path, persona_id: str = "default") -> dict[str, Any]:
    path = resolve_project_path(project_dir, Path("personas") / f"{str(persona_id or 'default').strip()}.json")
    payload = read_json(path, default={})
    if not isinstance(payload, dict):
        return {}
    return payload
