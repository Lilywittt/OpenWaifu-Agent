from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from io_utils import normalize_spaces
from workbench.store import workbench_inventory_paths


def _run_index_path(project_dir: Path) -> Path:
    inventory = workbench_inventory_paths(project_dir)
    return Path(str(inventory["runIndexJsonlPath"])).resolve()


def capture_workbench_source_cursor(project_dir: Path) -> dict[str, Any]:
    path = _run_index_path(project_dir)
    line_count = 0
    if path.exists():
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            line_count = sum(1 for _ in handle)
    return {"lineCount": line_count}


def _read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            if isinstance(payload, dict):
                records.append(payload)
    return records


def _is_reportable_record(record: dict[str, Any]) -> bool:
    if bool(record.get("deleted", False)):
        return False
    if normalize_spaces(str(record.get("status", ""))) != "completed":
        return False
    if not normalize_spaces(str(record.get("runId", ""))):
        return False
    if not normalize_spaces(str(record.get("generatedImagePath", ""))):
        return False
    if not normalize_spaces(str(record.get("socialPostPreview", ""))):
        return False
    return True


def list_new_reportable_run_records(
    project_dir: Path,
    cursor: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = _run_index_path(project_dir)
    records = _read_jsonl_records(path)
    current_line_count = len(records)
    previous_line_count = 0
    if isinstance(cursor, dict):
        try:
            previous_line_count = max(int(cursor.get("lineCount", 0) or 0), 0)
        except (TypeError, ValueError):
            previous_line_count = 0
    if current_line_count < previous_line_count:
        return ([], {"lineCount": current_line_count})
    fresh_records = records[previous_line_count:]
    reportable_records = [record for record in fresh_records if _is_reportable_record(record)]
    return (reportable_records, {"lineCount": current_line_count})
