from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import ensure_dir, read_json, write_json
from runtime_layout import sanitize_segment

from .qq_bot_private_ui import MODE_DEVELOPER, MODE_EXPERIENCE, normalize_private_mode
from .state import publish_state_root


DEFAULT_PENDING_ACTION = ""
PENDING_ACTION_SCENE_DRAFT = "scene_draft_injection"


def qq_bot_private_state_root(project_dir: Path) -> Path:
    return ensure_dir(publish_state_root(project_dir) / "qq_bot_private_state")


def _user_state_path(project_dir: Path, user_openid: str) -> Path:
    safe_name = sanitize_segment(user_openid) or "user"
    return qq_bot_private_state_root(project_dir) / "users" / f"{safe_name}.json"


def _default_state(user_openid: str) -> dict[str, Any]:
    return {
        "userOpenId": str(user_openid).strip(),
        "mode": MODE_EXPERIENCE,
        "pendingAction": DEFAULT_PENDING_ACTION,
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
    }


def load_private_user_state(project_dir: Path, user_openid: str) -> dict[str, Any]:
    path = _user_state_path(project_dir, user_openid)
    if not path.exists():
        return _default_state(user_openid)
    try:
        payload = read_json(path)
    except Exception:
        return _default_state(user_openid)
    if not isinstance(payload, dict):
        return _default_state(user_openid)
    return {
        "userOpenId": str(payload.get("userOpenId", user_openid)).strip() or str(user_openid).strip(),
        "mode": normalize_private_mode(str(payload.get("mode", MODE_EXPERIENCE))),
        "pendingAction": str(payload.get("pendingAction", DEFAULT_PENDING_ACTION)).strip(),
        "updatedAt": str(payload.get("updatedAt", "")).strip(),
    }


def save_private_user_state(project_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    user_openid = str(payload.get("userOpenId", "")).strip()
    if not user_openid:
        raise RuntimeError("private user state requires userOpenId")
    normalized = {
        "userOpenId": user_openid,
        "mode": normalize_private_mode(str(payload.get("mode", MODE_EXPERIENCE))),
        "pendingAction": str(payload.get("pendingAction", DEFAULT_PENDING_ACTION)).strip(),
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
    }
    path = _user_state_path(project_dir, user_openid)
    ensure_dir(path.parent)
    write_json(path, normalized)
    return normalized


def set_private_user_mode(project_dir: Path, user_openid: str, mode: str) -> dict[str, Any]:
    state = load_private_user_state(project_dir, user_openid)
    state["mode"] = normalize_private_mode(mode)
    state["pendingAction"] = DEFAULT_PENDING_ACTION
    return save_private_user_state(project_dir, state)


def set_private_user_pending_action(project_dir: Path, user_openid: str, pending_action: str) -> dict[str, Any]:
    state = load_private_user_state(project_dir, user_openid)
    state["pendingAction"] = str(pending_action or "").strip()
    return save_private_user_state(project_dir, state)


def clear_private_user_pending_action(project_dir: Path, user_openid: str) -> dict[str, Any]:
    return set_private_user_pending_action(project_dir, user_openid, DEFAULT_PENDING_ACTION)
