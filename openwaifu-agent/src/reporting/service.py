from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from io_utils import read_json

from .adapters.qq_report import send_workbench_report_to_qq
from .package import build_workbench_report_package
from .sources import capture_workbench_source_cursor, list_new_reportable_run_records
from .state import (
    append_sent_report_record,
    append_service_event,
    clear_service_lock,
    clear_service_stop_request,
    is_service_stop_requested,
    read_sent_run_ids,
    write_service_lock,
    write_service_status,
)


DEFAULT_POLL_SECONDS = 5


def load_workbench_report_service_config(
    project_dir: Path,
    config_path: Path | None = None,
) -> dict[str, Any]:
    resolved_path = config_path or (project_dir / "config" / "reporting" / "workbench_report_service.json")
    payload = read_json(resolved_path)
    if not isinstance(payload, dict):
        raise RuntimeError("workbench report service config must be a JSON object.")
    qq_target = payload.get("qqTarget")
    if not isinstance(qq_target, dict) or not qq_target:
        raise RuntimeError("workbench report service config must contain qqTarget.")
    poll_seconds = int(payload.get("pollSeconds", DEFAULT_POLL_SECONDS) or DEFAULT_POLL_SECONDS)
    if poll_seconds <= 0:
        raise RuntimeError("workbench report service pollSeconds must be greater than 0.")
    return {
        **payload,
        "pollSeconds": poll_seconds,
        "qqTarget": dict(qq_target),
    }


def poll_workbench_report_once(
    project_dir: Path,
    *,
    source_cursor: dict[str, Any],
    sent_run_ids: set[str],
    target_config: dict[str, Any],
    log: Callable[[str], None],
    send_report: Callable[..., dict[str, Any]] = send_workbench_report_to_qq,
) -> tuple[dict[str, Any], dict[str, int]]:
    records, next_cursor = list_new_reportable_run_records(project_dir, source_cursor)
    stats: dict[str, Any] = {"reported": 0, "skipped": 0, "lastRunId": ""}
    for record in records:
        run_id = str(record.get("runId", "")).strip()
        if not run_id:
            stats["skipped"] += 1
            continue
        if run_id in sent_run_ids:
            stats["skipped"] += 1
            append_service_event(
                project_dir,
                {
                    "event": "skip_duplicate_run",
                    "runId": run_id,
                },
            )
            continue
        report_package = build_workbench_report_package(project_dir, record)
        if report_package is None:
            stats["skipped"] += 1
            append_service_event(
                project_dir,
                {
                    "event": "skip_unreportable_run",
                    "runId": run_id,
                },
            )
            continue
        receipt = send_report(
            project_dir=project_dir,
            target_config=target_config,
            report_package=report_package,
        )
        sent_run_ids.add(run_id)
        stats["reported"] += 1
        append_sent_report_record(
            project_dir,
            {
                "runId": run_id,
                "runRoot": str(report_package.get("runRoot", "")),
                "imagePath": str(report_package.get("imagePath", "")),
                "socialPostText": str(report_package.get("socialPostText", "")),
                "receipt": receipt,
            },
        )
        append_service_event(
            project_dir,
            {
                "event": "report_sent",
                "runId": run_id,
                "messageId": str(receipt.get("messageId", "")),
            },
        )
        stats["lastRunId"] = run_id
        log(f"[workbench-report] 已推送 run={run_id}")
    return next_cursor, stats


def run_workbench_report_service(
    project_dir: Path,
    *,
    config_path: Path | None = None,
    poll_seconds: int = 0,
    log: Callable[[str], None] | None = None,
) -> int:
    resolved_project_dir = Path(project_dir).resolve()
    service_log = log or (lambda message: None)
    config = load_workbench_report_service_config(resolved_project_dir, config_path)
    effective_poll_seconds = int(poll_seconds or config["pollSeconds"])
    if effective_poll_seconds <= 0:
        effective_poll_seconds = DEFAULT_POLL_SECONDS

    clear_service_stop_request(resolved_project_dir)
    write_service_lock(
        resolved_project_dir,
        {
            "pid": os.getpid(),
            "startedAt": datetime.now().isoformat(timespec="seconds"),
            "configPath": str((config_path or (resolved_project_dir / "config" / "reporting" / "workbench_report_service.json")).resolve()),
            "pollSeconds": effective_poll_seconds,
        },
    )
    source_cursor = capture_workbench_source_cursor(resolved_project_dir)
    sent_run_ids = read_sent_run_ids(resolved_project_dir)
    reported_count = 0
    skipped_count = 0
    last_reported_run_id = ""
    write_service_status(
        resolved_project_dir,
        {
            "status": "running",
            "stage": "监听新完成 run",
            "startedAt": datetime.now().isoformat(timespec="seconds"),
            "pollSeconds": effective_poll_seconds,
            "cursor": source_cursor,
            "reportedCount": reported_count,
            "skippedCount": skipped_count,
            "lastReportedRunId": "",
            "error": "",
        },
    )
    append_service_event(
        resolved_project_dir,
        {
            "event": "service_started",
            "cursor": source_cursor,
        },
    )

    try:
        while True:
            if is_service_stop_requested(resolved_project_dir):
                write_service_status(
                    resolved_project_dir,
                    {
                        "status": "stopped",
                        "stage": "已停止",
                        "finishedAt": datetime.now().isoformat(timespec="seconds"),
                        "pollSeconds": effective_poll_seconds,
                        "cursor": source_cursor,
                        "reportedCount": reported_count,
                        "skippedCount": skipped_count,
                        "lastReportedRunId": last_reported_run_id,
                        "error": "",
                    },
                )
                append_service_event(resolved_project_dir, {"event": "service_stopped"})
                return 0
            source_cursor, stats = poll_workbench_report_once(
                resolved_project_dir,
                source_cursor=source_cursor,
                sent_run_ids=sent_run_ids,
                target_config=config["qqTarget"],
                log=service_log,
            )
            reported_count += int(stats["reported"])
            skipped_count += int(stats["skipped"])
            if stats["reported"] > 0:
                last_reported_run_id = str(stats.get("lastRunId", "")).strip() or last_reported_run_id
            write_service_status(
                resolved_project_dir,
                {
                    "status": "running",
                    "stage": "监听新完成 run",
                    "pollSeconds": effective_poll_seconds,
                    "cursor": source_cursor,
                    "reportedCount": reported_count,
                    "skippedCount": skipped_count,
                    "lastReportedRunId": last_reported_run_id,
                    "error": "",
                },
            )
            time.sleep(effective_poll_seconds)
    except KeyboardInterrupt:
        write_service_status(
            resolved_project_dir,
            {
                "status": "stopped",
                "stage": "已停止",
                "finishedAt": datetime.now().isoformat(timespec="seconds"),
                "pollSeconds": effective_poll_seconds,
                "cursor": source_cursor,
                "reportedCount": reported_count,
                "skippedCount": skipped_count,
                "lastReportedRunId": last_reported_run_id,
                "error": "",
            },
        )
        append_service_event(resolved_project_dir, {"event": "service_stopped"})
        return 0
    except Exception as exc:
        append_service_event(
            resolved_project_dir,
            {
                "event": "service_failed",
                "error": str(exc),
            },
        )
        write_service_status(
            resolved_project_dir,
            {
                "status": "failed",
                "stage": "",
                "finishedAt": datetime.now().isoformat(timespec="seconds"),
                "pollSeconds": effective_poll_seconds,
                "cursor": source_cursor,
                "reportedCount": reported_count,
                "skippedCount": skipped_count,
                "lastReportedRunId": last_reported_run_id,
                "error": str(exc),
            },
        )
        raise
    finally:
        clear_service_stop_request(resolved_project_dir)
        clear_service_lock(resolved_project_dir)
