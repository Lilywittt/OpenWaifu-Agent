from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from io_utils import ensure_dir, write_json
from runtime_layout import sanitize_segment

from .state import publish_state_root


REQUIRED_SCENE_DRAFT_KEYS = ("worldSceneZh",)
MAX_SCENE_DRAFT_HISTORY_PER_USER = 20


def qq_bot_scene_drafts_root(project_dir: Path) -> Path:
    return ensure_dir(publish_state_root(project_dir) / "qq_bot_scene_drafts")


def _user_scene_draft_root(project_dir: Path, user_openid: str) -> Path:
    safe_user = sanitize_segment(user_openid) or "user"
    return ensure_dir(qq_bot_scene_drafts_root(project_dir) / safe_user)


def latest_scene_draft_path(project_dir: Path, user_openid: str) -> Path:
    return _user_scene_draft_root(project_dir, user_openid) / "latest.json"


def _allocate_history_entry_path(history_dir: Path) -> Path:
    base_name = datetime.now().strftime("%Y-%m-%dT%H-%M-%S-%f")[:-3]
    candidate = history_dir / f"{base_name}.json"
    suffix = 1
    while candidate.exists():
        candidate = history_dir / f"{base_name}_{suffix:02d}.json"
        suffix += 1
    return candidate


def _prune_history_entries(history_dir: Path) -> None:
    entries = sorted((path for path in history_dir.glob("*.json") if path.is_file()), key=lambda path: path.name)
    excess = max(len(entries) - MAX_SCENE_DRAFT_HISTORY_PER_USER, 0)
    for stale_dir in entries[:excess]:
        try:
            stale_dir.unlink()
        except OSError:
            pass


def _strip_code_fence(raw_text: str) -> str:
    text = str(raw_text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return text


def parse_scene_draft_message(raw_text: str) -> dict[str, str]:
    text = _strip_code_fence(raw_text)
    if not text:
        raise RuntimeError("场景设计内容不能为空。")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        if text.startswith("{") or text.startswith("["):
            raise RuntimeError("场景设计稿 JSON 格式不正确。") from exc
        return {
            "scenePremiseZh": "",
            "worldSceneZh": text,
        }
    if not isinstance(payload, dict):
        raise RuntimeError("场景设计稿 JSON 必须是对象。")

    normalized = {
        "scenePremiseZh": str(payload.get("scenePremiseZh", "")).strip(),
        "worldSceneZh": str(payload.get("worldSceneZh", "")).strip(),
    }
    missing = [key for key in REQUIRED_SCENE_DRAFT_KEYS if not normalized[key]]
    if missing:
        raise RuntimeError(f"场景设计稿缺少必填字段：{', '.join(missing)}")
    return normalized


def persist_scene_draft_message(project_dir: Path, *, user_openid: str, scene_draft: dict[str, Any]) -> Path:
    user_root = _user_scene_draft_root(project_dir, user_openid)
    history_dir = ensure_dir(user_root / "history")

    target_path = user_root / "latest.json"
    write_json(target_path, scene_draft)

    history_path = _allocate_history_entry_path(history_dir)
    write_json(history_path, scene_draft)
    _prune_history_entries(history_dir)
    return target_path
