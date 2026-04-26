from __future__ import annotations

from pathlib import Path
from typing import Any

from io_utils import normalize_spaces, read_json
from path_policy import resolve_workspace_path

from .adapters import browser_automation_adapter_names
from .browser_profiles import (
    load_publish_local_config,
    publish_local_config_path,
    read_edge_publish_profile_status,
)

from .contracts import (
    BROWSER_SAVE_EXECUTOR,
    LOCAL_DIRECTORY_TARGET_ID,
    LOCAL_SAVE_AS_TARGET_ID,
    SERVER_PUBLISH_EXECUTOR,
)
from .local_export import (
    default_local_export_name,
    local_export_capability_payload,
    normalize_local_export_options,
)


TARGETS_CONFIG_PATH = "config/publish/targets.json"
BROWSER_AUTOMATION_ADAPTERS = browser_automation_adapter_names()


def publish_targets_config_path(project_dir: Path, targets_path: Path | None = None) -> Path:
    if targets_path is not None:
        return Path(targets_path).resolve()
    return (Path(project_dir).resolve() / TARGETS_CONFIG_PATH).resolve()


def publish_targets_local_config_path(project_dir: Path) -> Path:
    return publish_local_config_path(project_dir)


def load_publish_targets_config(project_dir: Path, targets_path: Path | None = None) -> dict[str, Any]:
    resolved_path = publish_targets_config_path(project_dir, targets_path)
    payload = read_json(resolved_path)
    targets = payload.get("targets", {})
    if not isinstance(targets, dict) or not targets:
        raise RuntimeError("发布目标配置缺少 targets。")
    default_target_ids = payload.get("defaultTargetIds", [])
    if not isinstance(default_target_ids, list) or not default_target_ids:
        raise RuntimeError("发布目标配置缺少 defaultTargetIds。")
    for target_id in default_target_ids:
        if target_id not in targets:
            raise RuntimeError(f"默认发布目标不存在：{target_id}")
    return payload


def resolve_publish_targets(targets_config: dict[str, Any], target_ids: list[str] | tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    configured_targets = targets_config["targets"]
    resolved_ids = list(target_ids) if target_ids else list(targets_config["defaultTargetIds"])
    if not resolved_ids:
        raise RuntimeError("没有选中任何发布目标。")
    resolved_targets: list[dict[str, Any]] = []
    for target_id in resolved_ids:
        if target_id not in configured_targets:
            raise RuntimeError(f"未知发布目标：{target_id}")
        target_config = dict(configured_targets[target_id])
        target_config["targetId"] = target_id
        resolved_targets.append(target_config)
    return resolved_targets


def load_publish_targets_local_config(project_dir: Path) -> dict[str, Any]:
    return load_publish_local_config(project_dir)


def _normalize_preset(project_dir: Path, payload: dict[str, Any]) -> dict[str, str] | None:
    preset_id = normalize_spaces(str(payload.get("id", "")))
    label = normalize_spaces(str(payload.get("label", "")))
    raw_path = normalize_spaces(str(payload.get("path", "")))
    if not preset_id or not label or not raw_path:
        return None
    return {
        "id": preset_id,
        "label": label,
        "path": str(resolve_workspace_path(project_dir, raw_path)),
    }


def _target_descriptor(raw_target: dict[str, Any], edge_status: dict[str, Any]) -> dict[str, Any]:
    adapter = normalize_spaces(str(raw_target.get("adapter", "")))
    description = normalize_spaces(str(raw_target.get("description", "")))
    if adapter in BROWSER_AUTOMATION_ADAPTERS:
        ready = bool(edge_status.get("readyForPublish"))
        uses_target_profile = (
            normalize_spaces(str(raw_target.get("browserProfilePersistence", ""))).casefold() == "target"
        )
        guidance = normalize_spaces(str(edge_status.get("guidance", "")))
        if ready and uses_target_profile:
            guidance = "登录态过期时，在打开的目标发布窗口完成登录，然后重新触发发布。"
        return {
            "requiresBrowserProfile": True,
            "browserProfile": "edge",
            "available": ready,
            "statusText": normalize_spaces(str(edge_status.get("statusText", ""))),
            "guidance": guidance,
            "setupCommand": normalize_spaces(
                str(edge_status.get("statusCommand" if ready else "syncCommand", ""))
            ),
            "description": description or "使用 Edge 登录态打开平台页面并填好草稿。",
            "supportsLocalExport": False,
            "defaultLocalExportKind": "",
            "localExportKinds": [],
        }
    return {
        "requiresBrowserProfile": False,
        "browserProfile": "",
        "available": True,
        "statusText": "可用",
        "guidance": "",
        "setupCommand": "",
        "description": description,
        "supportsLocalExport": False,
        "defaultLocalExportKind": "",
        "localExportKinds": [],
    }


def _ensure_publish_target_available(project_dir: Path, target_config: dict[str, Any]) -> None:
    adapter = normalize_spaces(str(target_config.get("adapter", "")))
    if adapter not in BROWSER_AUTOMATION_ADAPTERS:
        return
    edge_status = read_edge_publish_profile_status(project_dir)
    if bool(edge_status.get("readyForPublish")):
        return
    display_name = normalize_spaces(str(target_config.get("displayName", ""))) or normalize_spaces(
        str(target_config.get("targetId", "浏览器发布目标"))
    )
    guidance = normalize_spaces(str(edge_status.get("guidance", "")))
    raise RuntimeError(f"{display_name} 需要先完成 Edge 发布配置。{guidance}")


def list_publish_targets(project_dir: Path, targets_path: Path | None = None) -> dict[str, Any]:
    config = load_publish_targets_config(project_dir, targets_path)
    local_config = load_publish_targets_local_config(project_dir)
    configured_targets: list[dict[str, Any]] = []
    edge_status = read_edge_publish_profile_status(project_dir)
    for target_id, raw_target in config["targets"].items():
        if not isinstance(raw_target, dict):
            continue
        configured_targets.append(
            {
                "id": target_id,
                "displayName": normalize_spaces(str(raw_target.get("displayName", ""))) or target_id,
                "adapter": normalize_spaces(str(raw_target.get("adapter", ""))),
                "executor": SERVER_PUBLISH_EXECUTOR,
                "internal": bool(raw_target.get("internal", False)),
                "requiresLocalDirectory": False,
                "configured": True,
                **_target_descriptor(raw_target, edge_status),
            }
        )
    configured_targets.append(
        {
            "id": LOCAL_DIRECTORY_TARGET_ID,
            "displayName": "服务端目录导出",
            "adapter": LOCAL_DIRECTORY_TARGET_ID,
            "executor": SERVER_PUBLISH_EXECUTOR,
            "internal": True,
            "requiresLocalDirectory": True,
            "configured": False,
            "requiresBrowserProfile": False,
            "browserProfile": "",
            "available": True,
            "statusText": "可用",
            "guidance": "",
            "setupCommand": "",
            "description": "给脚本和自动化流程使用的目录导出能力。",
            **local_export_capability_payload(),
        }
    )
    configured_targets.append(
        {
            "id": LOCAL_SAVE_AS_TARGET_ID,
            "displayName": "本地另存为",
            "adapter": BROWSER_SAVE_EXECUTOR,
            "executor": BROWSER_SAVE_EXECUTOR,
            "internal": False,
            "requiresLocalDirectory": False,
            "configured": False,
            "requiresBrowserProfile": False,
            "browserProfile": "",
            "available": True,
            "statusText": "可用",
            "guidance": "",
            "setupCommand": "",
            "description": "选择目录，保存最终图片和社媒文案。",
            **local_export_capability_payload(),
        }
    )
    presets = []
    for item in local_config.get("localDirectoryPresets", []) or []:
        if isinstance(item, dict):
            preset = _normalize_preset(project_dir, item)
            if preset is not None:
                presets.append(preset)
    return {
        "targets": configured_targets,
        "defaultTargetIds": list(config.get("defaultTargetIds", [])),
        "localDirectoryPresets": presets,
        "localConfigPath": str(publish_targets_local_config_path(project_dir)),
        "browserProfiles": {
            "edge": edge_status,
        },
    }


def _resolve_local_export_options(options: dict[str, Any] | None, publish_input: dict[str, Any] | None) -> dict[str, str]:
    payload = options if isinstance(options, dict) else {}
    return normalize_local_export_options(
        payload.get("localExport", {}),
        default_name=default_local_export_name(publish_input),
    )


def build_local_directory_target(
    local_directory: str,
    *,
    options: dict[str, Any] | None = None,
    publish_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    directory_path = normalize_spaces(local_directory)
    if not directory_path:
        raise RuntimeError("本地目录不能为空。")
    return {
        "targetId": LOCAL_DIRECTORY_TARGET_ID,
        "adapter": LOCAL_DIRECTORY_TARGET_ID,
        "displayName": "本地目录",
        "directoryPath": directory_path,
        "localExport": _resolve_local_export_options(options, publish_input),
    }


def resolve_publish_targets_for_request(
    project_dir: Path,
    *,
    target_ids: list[str] | tuple[str, ...],
    local_directory: str = "",
    options: dict[str, Any] | None = None,
    publish_input: dict[str, Any] | None = None,
    targets_path: Path | None = None,
) -> list[dict[str, Any]]:
    static_target_ids = [target_id for target_id in target_ids if target_id != LOCAL_DIRECTORY_TARGET_ID]
    static_targets = []
    if static_target_ids:
        static_targets = resolve_publish_targets(
            load_publish_targets_config(project_dir, targets_path),
            static_target_ids,
        )
        for target in static_targets:
            _ensure_publish_target_available(project_dir, target)
    if LOCAL_DIRECTORY_TARGET_ID in target_ids:
        static_targets.append(
            build_local_directory_target(
                local_directory,
                options=options,
                publish_input=publish_input,
            )
        )
    return static_targets
