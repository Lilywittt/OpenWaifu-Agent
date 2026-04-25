from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from io_utils import normalize_spaces


LOCAL_EXPORT_KIND_IMAGE_ONLY = "image_only"
LOCAL_EXPORT_KIND_BUNDLE_FOLDER = "bundle_folder"
DEFAULT_LOCAL_EXPORT_KIND = LOCAL_EXPORT_KIND_BUNDLE_FOLDER
DEFAULT_LOCAL_EXPORT_NAME = "openwaifu publish"
TEXT_FILE_SUFFIX = "_social_post.txt"
LOCAL_EXPORT_KIND_ITEMS = (
    {
        "id": LOCAL_EXPORT_KIND_IMAGE_ONLY,
        "label": "只导出图片",
        "description": "只保存最终图片。",
    },
    {
        "id": LOCAL_EXPORT_KIND_BUNDLE_FOLDER,
        "label": "导出图文文件夹",
        "description": "保存最终图片和对应社媒文案。",
    },
)

_INVALID_FILE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_SPACE_PATTERN = re.compile(r"\s+")


def normalize_local_export_kind(raw_value: Any) -> str:
    candidate = normalize_spaces(str(raw_value))
    if candidate == LOCAL_EXPORT_KIND_IMAGE_ONLY:
        return LOCAL_EXPORT_KIND_IMAGE_ONLY
    return DEFAULT_LOCAL_EXPORT_KIND


def default_local_export_name(publish_input: dict[str, Any] | None = None) -> str:
    payload = publish_input if isinstance(publish_input, dict) else {}
    candidates = (
        payload.get("scenePremiseZh"),
        payload.get("subjectDisplayNameZh"),
        payload.get("runId"),
    )
    for value in candidates:
        normalized = normalize_spaces(str(value))
        if normalized:
            return normalized
    return DEFAULT_LOCAL_EXPORT_NAME


def sanitize_local_export_name(raw_value: Any, *, fallback: str = DEFAULT_LOCAL_EXPORT_NAME) -> str:
    normalized = normalize_spaces(str(raw_value)) or normalize_spaces(str(fallback)) or DEFAULT_LOCAL_EXPORT_NAME
    sanitized = _INVALID_FILE_CHARS.sub("_", normalized)
    sanitized = _SPACE_PATTERN.sub(" ", sanitized)
    sanitized = sanitized.strip(" .")
    sanitized = sanitized[:80].strip(" .")
    return sanitized or DEFAULT_LOCAL_EXPORT_NAME


def normalize_local_export_options(raw_value: Any, *, default_name: str) -> dict[str, str]:
    payload = raw_value if isinstance(raw_value, dict) else {}
    export_kind = normalize_local_export_kind(payload.get("kind"))
    export_name = sanitize_local_export_name(
        payload.get("name", ""),
        fallback=default_name,
    )
    return {
        "kind": export_kind,
        "name": export_name,
    }


def local_export_capability_payload() -> dict[str, Any]:
    return {
        "supportsLocalExport": True,
        "defaultLocalExportKind": DEFAULT_LOCAL_EXPORT_KIND,
        "localExportKinds": [dict(item) for item in LOCAL_EXPORT_KIND_ITEMS],
    }


def next_available_file_path(parent_dir: Path, *, base_name: str, suffix: str) -> Path:
    normalized_suffix = suffix or ""
    counter = 1
    while True:
        candidate_name = f"{base_name}{normalized_suffix}" if counter == 1 else f"{base_name} ({counter}){normalized_suffix}"
        candidate_path = parent_dir / candidate_name
        if not candidate_path.exists():
            return candidate_path
        counter += 1


def next_available_directory_path(parent_dir: Path, *, base_name: str) -> Path:
    counter = 1
    while True:
        candidate_name = base_name if counter == 1 else f"{base_name} ({counter})"
        candidate_path = parent_dir / candidate_name
        if not candidate_path.exists():
            return candidate_path
        counter += 1
