from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from io_utils import normalize_spaces
from .local_export import normalize_local_export_options


LOCAL_DIRECTORY_TARGET_ID = "local_directory"
LOCAL_SAVE_AS_TARGET_ID = "local_save_as"
SERVER_PUBLISH_EXECUTOR = "server"
BROWSER_SAVE_EXECUTOR = "browser_save"


@dataclass(frozen=True)
class PublishRunRequest:
    run_id: str
    target_ids: tuple[str, ...]
    local_directory: str
    options: dict[str, Any]


def _normalize_target_ids(raw_value: Any) -> tuple[str, ...]:
    if raw_value is None:
        return ()
    if isinstance(raw_value, str):
        candidate_values = [raw_value]
    elif isinstance(raw_value, (list, tuple)):
        candidate_values = list(raw_value)
    else:
        raise RuntimeError("发布目标格式无效。")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in candidate_values:
        if isinstance(item, dict):
            target_id = normalize_spaces(str(item.get("id", "")))
        else:
            target_id = normalize_spaces(str(item))
        if not target_id or target_id in seen:
            continue
        normalized.append(target_id)
        seen.add(target_id)
    return tuple(normalized)


def normalize_publish_run_request(payload: dict[str, Any]) -> PublishRunRequest:
    if not isinstance(payload, dict):
        raise RuntimeError("发布请求必须是 JSON 对象。")
    run_id = normalize_spaces(str(payload.get("runId", "")))
    if not run_id:
        raise RuntimeError("runId 不能为空。")
    raw_targets = payload.get("targetId")
    if raw_targets is None:
        raw_targets = payload.get("target")
    if raw_targets is None:
        raw_targets = payload.get("targets")
    if raw_targets is None:
        raw_targets = payload.get("targetIds")
    target_ids = list(_normalize_target_ids(raw_targets))
    local_directory = normalize_spaces(str(payload.get("localDirectory", "")))
    if local_directory and LOCAL_DIRECTORY_TARGET_ID not in target_ids:
        target_ids.append(LOCAL_DIRECTORY_TARGET_ID)
    if not target_ids:
        raise RuntimeError("请选择一个发布目标。")
    if len(target_ids) != 1:
        raise RuntimeError("一次发布只能选择一个目标。")
    raw_options = payload.get("options", {})
    options = dict(raw_options) if isinstance(raw_options, dict) else {}
    options["localExport"] = normalize_local_export_options(
        options.get("localExport", {}),
        default_name=run_id,
    )
    return PublishRunRequest(
        run_id=run_id,
        target_ids=tuple(target_ids),
        local_directory=local_directory,
        options=options,
    )
