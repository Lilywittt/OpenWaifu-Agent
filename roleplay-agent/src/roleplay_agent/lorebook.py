from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .io_utils import read_json


def load_lorebook(project_dir: Path) -> list[dict[str, Any]]:
    payload = read_json(project_dir / "lorebooks" / "default.json", default={"entries": []})
    entries = payload.get("entries", []) if isinstance(payload, dict) else []
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict) and bool(entry.get("enabled", True))]


def _key_matches(key: str, haystack: str) -> bool:
    text = str(key or "").strip()
    if not text:
        return False
    if len(text) >= 2 and text.startswith("/") and text.rfind("/") > 0:
        last_slash = text.rfind("/")
        pattern = text[1:last_slash]
        flags_text = text[last_slash + 1 :]
        flags = re.IGNORECASE if "i" in flags_text else 0
        try:
            return bool(re.search(pattern, haystack, flags=flags))
        except re.error:
            return False
    return text.casefold() in haystack.casefold()


def activate_lore_entries(project_dir: Path, context_text: str) -> list[dict[str, Any]]:
    haystack = str(context_text or "")
    activated: list[dict[str, Any]] = []
    for entry in load_lorebook(project_dir):
        content = str(entry.get("content", "")).strip()
        if not content:
            continue
        keys = entry.get("keys", [])
        always_active = bool(entry.get("alwaysActive", False))
        matched = always_active
        if isinstance(keys, list):
            matched = matched or any(_key_matches(str(key), haystack) for key in keys)
        if matched:
            activated.append(entry)
    activated.sort(key=lambda item: int(item.get("order", 0) or 0))
    return activated


def activated_lore_text(project_dir: Path, context_text: str) -> str:
    parts: list[str] = []
    for entry in activate_lore_entries(project_dir, context_text):
        content = str(entry.get("content", "")).strip()
        if content:
            parts.append(content)
    return "\n\n".join(parts).strip()
