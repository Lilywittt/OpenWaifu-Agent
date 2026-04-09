from __future__ import annotations

from datetime import datetime
from pathlib import Path

from io_utils import write_json


def extract_user_openid(payload: dict) -> str:
    event_data = payload.get("d", {})
    author = event_data.get("author", {})
    user_openid = str(author.get("user_openid", "")).strip()
    if user_openid:
        return user_openid
    return str(author.get("id", "")).strip()


def _upsert_env_value(env_path: Path, key: str, value: str) -> None:
    lines = []
    found = False
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8-sig").splitlines()
    updated: list[str] = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            updated.append(f"{key}={value}")
            found = True
        else:
            updated.append(line)
    if not found:
        updated.append(f"{key}={value}")
    env_path.write_text("\n".join(updated).strip() + "\n", encoding="utf-8")


def persist_user_openid(project_dir: Path, *, state_root: Path, user_openid: str, event_path: Path) -> Path:
    openid = str(user_openid or "").strip()
    if not openid:
        raise RuntimeError("user_openid is empty.")
    latest_path = state_root / "latest_user_openid.json"
    write_json(
        latest_path,
        {
            "capturedAt": datetime.now().isoformat(timespec="seconds"),
            "userOpenId": openid,
            "eventPath": str(event_path),
        },
    )
    _upsert_env_value(project_dir / ".env", "QQ_BOT_USER_OPENID", openid)
    return latest_path
