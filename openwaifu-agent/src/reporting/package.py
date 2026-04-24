from __future__ import annotations

from pathlib import Path
from typing import Any

from io_utils import normalize_spaces
from run_detail_store import build_run_detail_snapshot


def _build_package_from_record(record: dict[str, Any]) -> dict[str, Any] | None:
    run_id = normalize_spaces(str(record.get("runId", "")))
    image_path = normalize_spaces(str(record.get("generatedImagePath", "")))
    social_post_text = normalize_spaces(str(record.get("socialPostPreview", "")))
    if not run_id or not image_path or not social_post_text:
        return None
    resolved_image_path = Path(image_path).resolve()
    if not resolved_image_path.exists() or not resolved_image_path.is_file():
        return None
    return {
        "runId": run_id,
        "runRoot": normalize_spaces(str(record.get("runRoot", ""))),
        "imagePath": str(resolved_image_path),
        "socialPostText": social_post_text,
        "sourceKind": normalize_spaces(str(record.get("sourceKind", ""))),
        "endStage": normalize_spaces(str(record.get("endStage", ""))),
    }


def build_workbench_report_package(project_dir: Path, record: dict[str, Any]) -> dict[str, Any] | None:
    run_id = normalize_spaces(str(record.get("runId", "")))
    if not run_id:
        return None
    detail = build_run_detail_snapshot(project_dir, run_id)
    if isinstance(detail, dict):
        image_path = normalize_spaces(str(detail.get("generatedImagePath", "")))
        social_post_text = normalize_spaces(str(detail.get("socialPostPreview", "")))
        if image_path and social_post_text:
            resolved_image_path = Path(image_path).resolve()
            if resolved_image_path.exists() and resolved_image_path.is_file():
                return {
                    "runId": run_id,
                    "runRoot": normalize_spaces(str(detail.get("runRoot", ""))),
                    "imagePath": str(resolved_image_path),
                    "socialPostText": social_post_text,
                    "sourceKind": normalize_spaces(str(record.get("sourceKind", ""))),
                    "endStage": normalize_spaces(str(record.get("endStage", ""))),
                }
    return _build_package_from_record(record)

