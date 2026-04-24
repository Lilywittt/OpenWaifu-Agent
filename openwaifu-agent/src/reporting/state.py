from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import ensure_dir, write_json
from process_utils import is_process_alive
from runtime_layout import runtime_root


SERVICE_DIRNAME = "workbench_report_service"


def reporting_state_root(project_dir: Path) -> Path:
    return ensure_dir(runtime_root(project_dir) / "service_state" / "reporting" / SERVICE_DIRNAME)


def reporting_logs_root(project_dir: Path) -> Path:
    return ensure_dir(runtime_root(project_dir) / "service_logs" / "reporting")


def service_lock_path(project_dir: Path) -> Path:
    return reporting_state_root(project_dir) / "service_lock.json"


def service_status_path(project_dir: Path) -> Path:
    return reporting_state_root(project_dir) / "latest_status.json"


def service_events_path(project_dir: Path) -> Path:
    return reporting_state_root(project_dir) / "service_events.jsonl"


def stop_request_path(project_dir: Path) -> Path:
    return reporting_state_root(project_dir) / "stop_requested.json"


def sent_reports_path(project_dir: Path) -> Path:
    return reporting_state_root(project_dir) / "sent_reports.jsonl"


def read_service_lock(project_dir: Path) -> dict[str, Any] | None:
    path = service_lock_path(project_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def write_service_lock(project_dir: Path, payload: dict[str, Any]) -> Path:
    path = service_lock_path(project_dir)
    write_json(path, payload)
    return path


def clear_service_lock(project_dir: Path) -> None:
    try:
        service_lock_path(project_dir).unlink()
    except (FileNotFoundError, OSError):
        return


def cleanup_stale_service_lock(project_dir: Path) -> bool:
    payload = read_service_lock(project_dir)
    if not payload:
        return False
    if is_process_alive(payload.get("pid")):
        return False
    clear_service_lock(project_dir)
    return True


def is_service_running(project_dir: Path) -> bool:
    payload = read_service_lock(project_dir)
    if not payload:
        return False
    return is_process_alive(payload.get("pid"))


def read_service_status(project_dir: Path) -> dict[str, Any] | None:
    path = service_status_path(project_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def write_service_status(project_dir: Path, payload: dict[str, Any]) -> Path:
    path = service_status_path(project_dir)
    write_json(
        path,
        {
            **payload,
            "updatedAt": datetime.now().isoformat(timespec="seconds"),
        },
    )
    return path


def append_service_event(project_dir: Path, payload: dict[str, Any]) -> Path:
    path = service_events_path(project_dir)
    ensure_dir(path.parent)
    record = {
        **payload,
        "recordedAt": datetime.now().isoformat(timespec="seconds"),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def request_service_stop(project_dir: Path, *, reason: str = "manual stop") -> Path:
    path = stop_request_path(project_dir)
    write_json(
        path,
        {
            "reason": str(reason).strip() or "manual stop",
            "requestedAt": datetime.now().isoformat(timespec="seconds"),
        },
    )
    return path


def is_service_stop_requested(project_dir: Path) -> bool:
    return stop_request_path(project_dir).exists()


def clear_service_stop_request(project_dir: Path) -> None:
    try:
        stop_request_path(project_dir).unlink()
    except (FileNotFoundError, OSError):
        return


def read_sent_report_records(project_dir: Path) -> list[dict[str, Any]]:
    path = sent_reports_path(project_dir)
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


def read_sent_run_ids(project_dir: Path) -> set[str]:
    return {
        str(record.get("runId", "")).strip()
        for record in read_sent_report_records(project_dir)
        if str(record.get("runId", "")).strip()
    }


def append_sent_report_record(project_dir: Path, payload: dict[str, Any]) -> Path:
    path = sent_reports_path(project_dir)
    ensure_dir(path.parent)
    record = {
        **payload,
        "recordedAt": datetime.now().isoformat(timespec="seconds"),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path

