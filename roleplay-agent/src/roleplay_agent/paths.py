from __future__ import annotations

import re
from pathlib import Path


def resolve_project_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_project_path(project_dir: Path, raw_path: str | Path) -> Path:
    path = Path(str(raw_path))
    if path.is_absolute():
        return path.resolve()
    return (project_dir / path).resolve()


def safe_segment(value: str, *, fallback: str = "default") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    text = re.sub(r"[^0-9A-Za-z._-]+", "_", text)
    text = text.strip("._-")
    return text or fallback
