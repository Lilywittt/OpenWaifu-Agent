from __future__ import annotations

from collections import deque
from typing import Callable


MAX_HANDLED_MESSAGE_IDS = 500


def mask_user_openid(user_openid: str) -> str:
    text = str(user_openid or "").strip()
    if not text:
        return "unknown"
    if len(text) <= 8:
        return text
    return f"{text[:4]}...{text[-4:]}"


def emit_key_log(log: Callable[[str], None] | None, message: str) -> None:
    if log is None:
        return
    log(f"[qq-generate] {message}")


def remember_handled_message(
    source_message_id: str,
    handled_message_ids: set[str],
    handled_message_order: deque[str],
) -> None:
    if not source_message_id or source_message_id in handled_message_ids:
        return
    handled_message_ids.add(source_message_id)
    handled_message_order.append(source_message_id)
    while len(handled_message_order) > MAX_HANDLED_MESSAGE_IDS:
        stale_message_id = handled_message_order.popleft()
        handled_message_ids.discard(stale_message_id)
