from __future__ import annotations

from typing import Any

from .base import PublishAdapter
from .local_archive import publish_to_local_archive
from .qq_bot_user import publish_to_qq_bot_user


ADAPTERS: dict[str, PublishAdapter] = {
    "local_archive": publish_to_local_archive,
    "qq_bot_user": publish_to_qq_bot_user,
}


def get_publish_adapter(adapter_name: str) -> PublishAdapter:
    key = str(adapter_name or "").strip()
    if key not in ADAPTERS:
        raise RuntimeError(f"Unsupported publish adapter: {key or '<empty>'}")
    return ADAPTERS[key]
