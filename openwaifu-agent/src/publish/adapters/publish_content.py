from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def publish_title(publish_input: dict[str, Any], target_config: dict[str, Any]) -> str:
    configured = str(target_config.get("title", "")).strip()
    if configured:
        return configured
    return (
        str(publish_input.get("scenePremiseZh", "")).strip()
        or str(publish_input.get("subjectDisplayNameZh", "")).strip()
        or str(publish_input.get("runId", "")).strip()
    )


def publish_tags(publish_input: dict[str, Any], target_config: dict[str, Any]) -> list[str]:
    raw_tags = publish_input.get("socialTags", [])
    if not isinstance(raw_tags, list):
        return []
    tags: list[str] = []
    seen: set[str] = set()
    for item in raw_tags:
        tag = str(item).strip().lstrip("#")
        tag = " ".join(tag.split())
        key = tag.casefold()
        if not tag or key in seen:
            continue
        tags.append(tag[:40])
        seen.add(key)
        if len(tags) >= 8:
            break
    return tags


def _caption_social_tags(publish_input: dict[str, Any], target_config: dict[str, Any]) -> str:
    if not bool(target_config.get("includeSocialTagsInCaption", False)):
        return ""
    tags = publish_tags(publish_input, target_config)
    if not tags:
        return ""
    return " ".join(f"#{tag.replace(' ', '')}" for tag in tags if tag.replace(" ", ""))


def publish_caption(publish_input: dict[str, Any], target_config: dict[str, Any]) -> str:
    caption_prefix = str(target_config.get("captionPrefix", "")).strip()
    caption_suffix = str(target_config.get("captionSuffix", "")).strip()
    text = str(publish_input.get("socialPostText", "")).strip()
    tag_suffix = _caption_social_tags(publish_input, target_config)
    parts = [part for part in (caption_prefix, text, tag_suffix, caption_suffix) if part]
    return "\n\n".join(parts)


def receipt_base(
    *,
    target_id: str,
    adapter: str,
    status: str,
    page_url: str,
    port: int,
    user_data_dir: Path | str = "",
) -> dict[str, Any]:
    payload = {
        "targetId": target_id,
        "adapter": adapter,
        "status": status,
        "publishedAt": datetime.now().isoformat(timespec="seconds"),
        "postUrl": page_url,
        "browser": "edge",
        "remoteDebuggingPort": port,
    }
    if user_data_dir:
        payload["browserUserDataDir"] = str(user_data_dir)
    return payload
