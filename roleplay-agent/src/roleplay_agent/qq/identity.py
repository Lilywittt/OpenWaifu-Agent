from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..io_utils import write_json


def extract_user_openid(payload: dict) -> str:
    data = payload.get("d", {})
    author = data.get("author", {})
    user_openid = str(author.get("user_openid", "")).strip()
    if user_openid:
        return user_openid
    return str(author.get("id", "")).strip()


def persist_latest_user_openid(project_dir: Path, *, user_openid: str, event_path: Path) -> None:
    if not str(user_openid or "").strip():
        return
    write_json(
        project_dir / "runtime" / "qq_gateway" / "latest_user_openid.json",
        {
            "capturedAt": datetime.now().isoformat(timespec="seconds"),
            "userOpenId": str(user_openid).strip(),
            "eventPath": str(event_path),
        },
    )
