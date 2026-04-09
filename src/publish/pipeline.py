from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import read_json, write_json
from runtime_layout import sanitize_segment

from .adapters import get_publish_adapter
from .package import build_publish_input
from .state import append_published_record


TARGETS_PATH = "config/publish/targets.json"
INPUT_FILENAME = "00_publish_input.json"
PLAN_FILENAME = "01_publish_plan.json"
PACKAGE_FILENAME = "04_publish_package.json"
SUMMARY_FILENAME = "publish_summary.json"


def load_publish_targets(project_dir: Path, targets_path: Path | None = None) -> dict[str, Any]:
    resolved_path = targets_path or (project_dir / TARGETS_PATH)
    payload = read_json(resolved_path)
    targets = payload.get("targets", {})
    if not isinstance(targets, dict) or not targets:
        raise RuntimeError("publish targets config must contain a non-empty targets object.")
    default_target_ids = payload.get("defaultTargetIds", [])
    if not isinstance(default_target_ids, list) or not default_target_ids:
        raise RuntimeError("publish targets config must contain non-empty defaultTargetIds.")
    for target_id in default_target_ids:
        if target_id not in targets:
            raise RuntimeError(f"default publish target does not exist: {target_id}")
    return payload


def resolve_publish_targets(targets_config: dict[str, Any], target_ids: list[str] | None = None) -> list[dict[str, Any]]:
    configured_targets = targets_config["targets"]
    resolved_ids = target_ids or list(targets_config["defaultTargetIds"])
    if not resolved_ids:
        raise RuntimeError("No publish targets were selected.")
    resolved_targets: list[dict[str, Any]] = []
    for target_id in resolved_ids:
        if target_id not in configured_targets:
            raise RuntimeError(f"Unknown publish target: {target_id}")
        target_config = dict(configured_targets[target_id])
        target_config["targetId"] = target_id
        resolved_targets.append(target_config)
    return resolved_targets


def run_publish_stage(
    project_dir: Path,
    bundle,
    default_run_context: dict[str, Any],
    publish_input: dict[str, Any],
    *,
    targets_path: Path | None = None,
    target_ids: list[str] | None = None,
    explicit_targets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    write_json(bundle.publish_dir / INPUT_FILENAME, publish_input)

    if explicit_targets is not None:
        targets = [dict(target) for target in explicit_targets]
    else:
        targets_config = load_publish_targets(project_dir, targets_path)
        targets = resolve_publish_targets(targets_config, target_ids)
    publish_plan = {
        "meta": {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "runMode": default_run_context.get("runMode", "default"),
        },
        "defaultRunContext": default_run_context,
        "targets": targets,
    }
    write_json(bundle.publish_dir / PLAN_FILENAME, publish_plan)

    receipts: list[dict[str, Any]] = []
    for index, target in enumerate(targets, start=1):
        target_id = str(target["targetId"])
        request_filename = f"02_{index:02d}_{sanitize_segment(target_id)}_request.json"
        receipt_filename = f"03_{index:02d}_{sanitize_segment(target_id)}_receipt.json"
        request_payload = {
            "target": target,
            "publishInput": publish_input,
        }
        write_json(bundle.publish_dir / request_filename, request_payload)
        adapter = get_publish_adapter(str(target.get("adapter", "")))
        receipt = adapter(
            project_dir=project_dir,
            bundle=bundle,
            target_id=target_id,
            target_config=target,
            publish_input=publish_input,
        )
        write_json(bundle.publish_dir / receipt_filename, receipt)
        receipts.append(receipt)
        append_published_record(
            project_dir,
            {
                "runId": bundle.run_id,
                "targetId": target_id,
                "receipt": receipt,
            },
        )

    publish_package = {
        "meta": {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "runMode": default_run_context.get("runMode", "default"),
        },
        "defaultRunContext": default_run_context,
        "publishInput": publish_input,
        "receipts": receipts,
    }
    write_json(bundle.publish_dir / PACKAGE_FILENAME, publish_package)
    write_json(
        bundle.output_dir / SUMMARY_FILENAME,
        {
            "runId": bundle.run_id,
            "targetCount": len(receipts),
            "receipts": receipts,
        },
    )
    return publish_package


def run_publish_pipeline(
    project_dir: Path,
    bundle,
    default_run_context: dict[str, Any],
    character_assets: dict[str, Any],
    creative_package: dict[str, Any],
    social_post_package: dict[str, Any],
    execution_package: dict[str, Any],
    *,
    targets_path: Path | None = None,
    target_ids: list[str] | None = None,
    explicit_targets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    publish_input = build_publish_input(
        bundle=bundle,
        character_assets=character_assets,
        creative_package=creative_package,
        social_post_package=social_post_package,
        execution_package=execution_package,
    )
    return run_publish_stage(
        project_dir,
        bundle,
        default_run_context,
        publish_input,
        targets_path=targets_path,
        target_ids=target_ids,
        explicit_targets=explicit_targets,
    )
