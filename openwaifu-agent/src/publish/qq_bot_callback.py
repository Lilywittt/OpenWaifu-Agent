from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from io_utils import ensure_dir, write_json

from .qq_bot_identity import extract_user_openid
from .qq_bot_identity import persist_user_openid as persist_user_openid_to_state
from .state import publish_state_root


def qq_bot_callback_state_root(project_dir: Path) -> Path:
    return ensure_dir(publish_state_root(project_dir) / "qq_bot_callback")


def qq_bot_callback_events_root(project_dir: Path) -> Path:
    return ensure_dir(qq_bot_callback_state_root(project_dir) / "events")


def _normalize_secret(secret: str) -> bytes:
    text = str(secret or "").strip()
    if not text:
        raise RuntimeError("QQ bot callback secret is empty.")
    while len(text) < 32:
        text += text
    return text[:32].encode("utf-8")


def build_callback_verification_signature(*, app_secret: str, event_ts: str, plain_token: str) -> str:
    private_key = Ed25519PrivateKey.from_private_bytes(_normalize_secret(app_secret))
    payload = f"{str(event_ts)}{str(plain_token)}".encode("utf-8")
    return private_key.sign(payload).hex()


def build_callback_verification_response(*, app_secret: str, payload: dict[str, Any]) -> dict[str, str]:
    event_data = payload.get("d", {})
    plain_token = str(event_data.get("plain_token", "")).strip()
    event_ts = str(event_data.get("event_ts", "")).strip()
    if not plain_token or not event_ts:
        raise RuntimeError("QQ bot callback verification payload is missing plain_token or event_ts.")
    return {
        "plain_token": plain_token,
        "signature": build_callback_verification_signature(
            app_secret=app_secret,
            event_ts=event_ts,
            plain_token=plain_token,
        ),
    }


def save_callback_event(
    project_dir: Path,
    *,
    payload: dict[str, Any],
    headers: dict[str, Any],
    raw_body: str,
    callback_path: str,
) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    payload_id = str(payload.get("id", "")).strip() or stamp
    safe_id = payload_id.replace("/", "_").replace("\\", "_").replace(":", "_")
    event_path = qq_bot_callback_events_root(project_dir) / f"{stamp}_{safe_id}.json"
    write_json(
        event_path,
        {
            "receivedAt": datetime.now().isoformat(timespec="seconds"),
            "callbackPath": callback_path,
            "headers": headers,
            "rawBody": raw_body,
            "payload": payload,
        },
    )
    return event_path


def persist_user_openid(project_dir: Path, *, user_openid: str, event_path: Path) -> Path:
    return persist_user_openid_to_state(
        project_dir,
        state_root=qq_bot_callback_state_root(project_dir),
        user_openid=user_openid,
        event_path=event_path,
    )
