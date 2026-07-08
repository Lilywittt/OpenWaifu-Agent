from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .io_utils import ensure_dir
from .paths import safe_segment


def conversation_path(project_dir: Path, user_id: str) -> Path:
    return project_dir / "runtime" / "conversations" / f"{safe_segment(user_id)}.jsonl"


def append_message(project_dir: Path, user_id: str, *, role: str, content: str) -> None:
    text = str(content or "").strip()
    if not text:
        return
    payload = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "role": str(role),
        "content": text,
    }
    path = conversation_path(project_dir, user_id)
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def load_recent_messages(project_dir: Path, user_id: str, *, limit: int) -> list[dict[str, str]]:
    path = conversation_path(project_dir, user_id)
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        try:
            payload: Any = json.loads(line)
        except json.JSONDecodeError:
            continue
        role = str(payload.get("role", "")).strip()
        content = str(payload.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            rows.append({"role": role, "content": content})
    if limit <= 0:
        return []
    return rows[-limit:]


def clear_conversation(project_dir: Path, user_id: str) -> bool:
    path = conversation_path(project_dir, user_id)
    if not path.exists():
        return False
    path.unlink()
    return True
