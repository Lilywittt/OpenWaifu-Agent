from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import normalize_spaces

from test_pipeline import execute_workbench_task, validate_workbench_request
from .content_workbench_store import (
    append_history_record,
    append_run_index_record,
    clear_workbench_stop_request,
    finalize_workbench_runtime,
    is_workbench_stop_requested,
    read_active_request,
    write_active_worker,
    write_workbench_status,
)


def _finalize_terminal_payload(project_dir: Path, payload: dict[str, Any]) -> None:
    write_workbench_status(project_dir, payload)
    append_history_record(project_dir, payload)
    append_run_index_record(project_dir, payload)


def run_content_workbench_worker(project_dir: Path, request: dict[str, Any] | None = None) -> int:
    project_dir = Path(project_dir).resolve()
    normalized_request = validate_workbench_request(project_dir, request or read_active_request(project_dir) or {})
    started_at = datetime.now().isoformat(timespec="seconds")
    worker_pid = os.getpid()
    worker_ack_at = datetime.now().isoformat(timespec="seconds")
    bundle_context: dict[str, str] = {"runId": "", "runRoot": ""}

    write_active_worker(
        project_dir,
        {
            "pid": worker_pid,
            "startedAt": started_at,
            "request": normalized_request,
        },
    )

    def update_stage(stage: str) -> None:
        write_workbench_status(
            project_dir,
            {
                "status": "running",
                "stage": normalize_spaces(stage),
                "request": normalized_request,
                "startedAt": started_at,
                "runId": bundle_context["runId"],
                "runRoot": bundle_context["runRoot"],
                "workerPid": worker_pid,
                "workerAckAt": worker_ack_at,
                "error": "",
            },
        )

    def remember_bundle(bundle, _request: dict[str, Any]) -> None:
        bundle_context["runId"] = str(bundle.run_id)
        bundle_context["runRoot"] = str(bundle.root)
        write_workbench_status(
            project_dir,
            {
                "status": "running",
                "stage": "已创建运行目录",
                "request": normalized_request,
                "startedAt": started_at,
                "runId": bundle_context["runId"],
                "runRoot": bundle_context["runRoot"],
                "workerPid": worker_pid,
                "workerAckAt": worker_ack_at,
                "error": "",
            },
        )

    try:
        result = execute_workbench_task(
            project_dir,
            normalized_request,
            log=update_stage,
            should_abort=lambda: is_workbench_stop_requested(project_dir),
            on_bundle_created=remember_bundle,
        )
        summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
        bundle = result.get("bundle")
        finished_at = datetime.now().isoformat(timespec="seconds")
        if bundle is not None:
            bundle_context["runId"] = str(bundle.run_id)
            bundle_context["runRoot"] = str(bundle.root)
        _finalize_terminal_payload(
            project_dir,
            {
                "status": "completed",
                "stage": "测试完成",
                "request": normalized_request,
                "startedAt": started_at,
                "finishedAt": finished_at,
                "runId": bundle_context["runId"],
                "runRoot": bundle_context["runRoot"],
                "workerPid": worker_pid,
                "workerAckAt": worker_ack_at,
                "summaryPath": str(Path(bundle_context["runRoot"]) / "output" / "run_summary.json")
                if bundle_context["runRoot"]
                else "",
                "sceneDraftPremiseZh": normalize_spaces(str(summary.get("sceneDraftPremiseZh", ""))),
                "error": "",
            },
        )
        return 0
    except InterruptedError:
        finished_at = datetime.now().isoformat(timespec="seconds")
        _finalize_terminal_payload(
            project_dir,
            {
                "status": "interrupted",
                "stage": "",
                "request": normalized_request,
                "startedAt": started_at,
                "finishedAt": finished_at,
                "runId": bundle_context["runId"],
                "runRoot": bundle_context["runRoot"],
                "workerPid": worker_pid,
                "workerAckAt": worker_ack_at,
                "summaryPath": str(Path(bundle_context["runRoot"]) / "output" / "run_summary.json")
                if bundle_context["runRoot"]
                else "",
                "sceneDraftPremiseZh": "",
                "error": "当前测试已按请求中断。",
            },
        )
        return 1
    except Exception as exc:
        finished_at = datetime.now().isoformat(timespec="seconds")
        _finalize_terminal_payload(
            project_dir,
            {
                "status": "failed",
                "stage": "",
                "request": normalized_request,
                "startedAt": started_at,
                "finishedAt": finished_at,
                "runId": bundle_context["runId"],
                "runRoot": bundle_context["runRoot"],
                "workerPid": worker_pid,
                "workerAckAt": worker_ack_at,
                "summaryPath": str(Path(bundle_context["runRoot"]) / "output" / "run_summary.json")
                if bundle_context["runRoot"]
                else "",
                "sceneDraftPremiseZh": "",
                "error": normalize_spaces(str(exc)) or "内容测试失败。",
            },
        )
        return 1
    finally:
        clear_workbench_stop_request(project_dir)
        finalize_workbench_runtime(project_dir)
