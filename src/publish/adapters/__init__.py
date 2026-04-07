from __future__ import annotations

from typing import Any

from .base import PublishAdapter
from .local_archive import publish_to_local_archive


ADAPTERS: dict[str, PublishAdapter] = {
    "local_archive": publish_to_local_archive,
}


def get_publish_adapter(adapter_name: str) -> PublishAdapter:
    key = str(adapter_name or "").strip()
    if key not in ADAPTERS:
        raise RuntimeError(f"Unsupported publish adapter: {key or '<empty>'}")
    return ADAPTERS[key]
