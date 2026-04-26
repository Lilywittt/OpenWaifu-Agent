from __future__ import annotations

from typing import Any

from .base import PublishAdapter, PublishAdapterSpec
from .local_archive import publish_to_local_archive
from .local_directory import publish_to_local_directory
from .pixiv_browser_draft import publish_to_pixiv_browser_draft
from .instagram_browser_draft import publish_to_instagram_browser_draft
from .bilibili_dynamic import publish_to_bilibili_dynamic
from .qzone_browser_draft import publish_to_qzone_browser_draft
from .qq_bot_user import publish_to_qq_bot_user


ADAPTER_SPECS: dict[str, PublishAdapterSpec] = {
    "local_archive": PublishAdapterSpec("local_archive", publish_to_local_archive),
    "local_directory": PublishAdapterSpec("local_directory", publish_to_local_directory),
    "pixiv_browser_draft": PublishAdapterSpec(
        "pixiv_browser_draft",
        publish_to_pixiv_browser_draft,
        browser_automation=True,
    ),
    "instagram_browser_draft": PublishAdapterSpec(
        "instagram_browser_draft",
        publish_to_instagram_browser_draft,
        browser_automation=True,
    ),
    "bilibili_dynamic": PublishAdapterSpec(
        "bilibili_dynamic",
        publish_to_bilibili_dynamic,
        browser_automation=True,
    ),
    "qzone_browser_draft": PublishAdapterSpec(
        "qzone_browser_draft",
        publish_to_qzone_browser_draft,
        browser_automation=True,
    ),
    "qq_bot_user": PublishAdapterSpec("qq_bot_user", publish_to_qq_bot_user),
}

ADAPTERS: dict[str, PublishAdapter] = {name: spec.handler for name, spec in ADAPTER_SPECS.items()}


def get_publish_adapter_spec(adapter_name: str) -> PublishAdapterSpec:
    key = str(adapter_name or "").strip()
    if key not in ADAPTER_SPECS:
        raise RuntimeError(f"Unsupported publish adapter: {key or '<empty>'}")
    return ADAPTER_SPECS[key]


def get_publish_adapter(adapter_name: str) -> PublishAdapter:
    return get_publish_adapter_spec(adapter_name).handler


def is_browser_automation_adapter(adapter_name: str) -> bool:
    key = str(adapter_name or "").strip()
    spec = ADAPTER_SPECS.get(key)
    return bool(spec and spec.browser_automation)


def browser_automation_adapter_names() -> set[str]:
    return {name for name, spec in ADAPTER_SPECS.items() if spec.browser_automation}
