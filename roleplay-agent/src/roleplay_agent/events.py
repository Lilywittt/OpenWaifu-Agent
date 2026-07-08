from __future__ import annotations

from pathlib import Path
from typing import Any

from .io_utils import read_json


def load_active_events(project_dir: Path) -> list[dict[str, Any]]:
    payload = read_json(project_dir / "events" / "active_events.json", default={"events": []})
    events = payload.get("events", []) if isinstance(payload, dict) else []
    if not isinstance(events, list):
        return []
    result = [event for event in events if isinstance(event, dict) and bool(event.get("enabled", True))]
    result.sort(key=lambda item: int(item.get("priority", 0) or 0), reverse=True)
    return result


def active_events_text(project_dir: Path) -> str:
    parts: list[str] = []
    for event in load_active_events(project_dir):
        title = str(event.get("title", "")).strip()
        content = str(event.get("content", "")).strip()
        if not content:
            continue
        parts.append(f"{title}\n{content}" if title else content)
    return "\n\n".join(parts).strip()
