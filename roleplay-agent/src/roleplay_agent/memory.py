from __future__ import annotations

from pathlib import Path
from typing import Any

from .io_utils import read_json, write_json
from .paths import safe_segment


def memory_path(project_dir: Path, user_id: str) -> Path:
    return project_dir / "runtime" / "memory" / f"{safe_segment(user_id)}.json"


def load_memory(project_dir: Path, user_id: str) -> dict[str, Any]:
    path = memory_path(project_dir, user_id)
    payload = read_json(path, default={})
    if not isinstance(payload, dict):
        return {}
    return payload


def save_memory(project_dir: Path, user_id: str, payload: dict[str, Any]) -> None:
    write_json(memory_path(project_dir, user_id), payload)


def memory_summary_text(project_dir: Path, user_id: str) -> str:
    payload = load_memory(project_dir, user_id)
    fields = payload.get("fields", [])
    if isinstance(fields, list):
        field_parts: list[str] = []
        for field in fields:
            if not isinstance(field, dict):
                continue
            label = str(field.get("label", "")).strip()
            content = str(field.get("content", "")).strip()
            if label and content:
                field_parts.append(f"{label}\n{content}")
            elif content:
                field_parts.append(content)
        if field_parts:
            return "\n\n".join(field_parts).strip()
    summary = str(payload.get("summary", "")).strip()
    notes = payload.get("notes", [])
    parts: list[str] = []
    if summary:
        parts.append(summary)
    if isinstance(notes, list):
        for note in notes:
            text = str(note).strip()
            if text:
                parts.append(f"- {text}")
    return "\n".join(parts).strip()
