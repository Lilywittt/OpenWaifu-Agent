from __future__ import annotations

import json
import sqlite3
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from env import get_env_value
from io_utils import normalize_spaces
from run_detail_store import (
    build_run_detail_snapshot as build_generic_run_detail_snapshot,
    resolve_generated_image_artifact as resolve_generic_generated_image_artifact,
)
from runtime_layout import runs_root, runtime_root

from publish.qq_bot_job_queue import job_db_path
from publish.qq_bot_private_ui import normalize_stage_label
from publish.qq_bot_runtime_store import (
    is_service_running,
    qq_bot_generate_service_state_root,
    read_service_lock,
    read_service_status,
)
from publish.qq_bot_service_support import mask_user_openid


DEFAULT_QUEUE_LIMIT = 20
DEFAULT_RECENT_JOB_LIMIT = 12
DEFAULT_EVENT_LIMIT = 40
DEFAULT_RUN_LIMIT = 8
DEFAULT_LOG_TAIL_LINES = 30


def _service_logs_root(project_dir: Path) -> Path:
    return runtime_root(project_dir) / "service_logs" / "publish"


def _service_stdout_path(project_dir: Path) -> Path:
    return _service_logs_root(project_dir) / "qq_bot_generate_service.stdout.log"


def _service_stderr_path(project_dir: Path) -> Path:
    return _service_logs_root(project_dir) / "qq_bot_generate_service.stderr.log"


def _service_events_path(project_dir: Path) -> Path:
    return qq_bot_generate_service_state_root(project_dir) / "service_events.jsonl"


def _social_sampling_health_path(project_dir: Path) -> Path:
    return runtime_root(project_dir) / "service_state" / "social_sampling_health.json"


def _qq_bot_config_path(project_dir: Path) -> Path:
    return project_dir / "config" / "publish" / "qq_bot_message.json"


def _safe_read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _parse_iso_datetime(raw: str) -> datetime | None:
    text = normalize_spaces(raw)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _seconds_since(raw: str) -> int | None:
    parsed = _parse_iso_datetime(raw)
    if parsed is None:
        return None
    return max(int((datetime.now() - parsed).total_seconds()), 0)


def _status_label(status: str) -> str:
    return {
        "starting": "启动中",
        "listening": "监听中",
        "running": "执行中",
        "idle": "空闲",
        "stopping": "停止中",
        "stopped": "已停止",
        "reconnecting": "重连中",
        "error": "异常",
        "unknown": "未知",
    }.get(normalize_spaces(status), normalize_spaces(status) or "未知")


def _trim_preview(value: str, limit: int = 120) -> str:
    text = normalize_spaces(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _detail_route_for_run(run_id: str) -> str:
    return f"/runs/detail?runId={quote(run_id, safe='')}"


def is_qq_bot_run_id(run_id: str) -> bool:
    return "_qqbot_" in normalize_spaces(run_id)


def _read_dashboard_identity(project_dir: Path) -> dict[str, str]:
    config_payload = _safe_read_json(_qq_bot_config_path(project_dir)) or {}
    env_name = normalize_spaces(str(config_payload.get("botDisplayNameEnvName", ""))) or "QQ_BOT_DISPLAY_NAME"
    env_display_name = normalize_spaces(get_env_value(project_dir, env_name, ""))
    config_display_name = normalize_spaces(str(config_payload.get("botDisplayName", "")))
    bot_display_name = env_display_name or config_display_name
    project_name = project_dir.name
    dashboard_title = f"{bot_display_name} 运维面板" if bot_display_name else f"{project_name} 运维面板"
    return {
        "projectName": project_name,
        "botDisplayName": bot_display_name,
        "dashboardTitle": dashboard_title,
    }


def _tail_lines(path: Path, limit: int) -> list[str]:
    if limit <= 0 or not path.exists():
        return []
    lines: deque[str] = deque(maxlen=limit)
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                text = line.rstrip("\r\n")
                if text:
                    lines.append(text)
    except OSError:
        return []
    return list(lines)


def _tail_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    raw_records: list[dict[str, Any]] = []
    for line in _tail_lines(path, limit * 2):
        try:
            payload = json.loads(line)
        except Exception:
            raw_records.append(
                {
                    "type": "invalid_jsonl",
                    "recordedAt": "",
                    "message": _trim_preview(line, 200),
                }
            )
            continue
        if isinstance(payload, dict):
            raw_records.append(payload)

    normalized: list[dict[str, Any]] = []
    for record in raw_records[-limit:]:
        normalized.append(
            {
                "recordedAt": normalize_spaces(str(record.get("recordedAt", ""))),
                "type": normalize_spaces(str(record.get("type", ""))) or "unknown",
                "runId": normalize_spaces(str(record.get("runId", ""))),
                "userOpenIdMasked": mask_user_openid(str(record.get("userOpenId", ""))),
                "stage": normalize_spaces(str(record.get("stage", ""))),
                "stageLabel": normalize_stage_label(str(record.get("stage", ""))),
                "message": _trim_preview(str(record.get("message", "")), 200),
                "error": _trim_preview(str(record.get("error", "")), 200),
                "reason": _trim_preview(str(record.get("reason", "")), 160),
            }
        )
    normalized.reverse()
    return normalized


def _connect_readonly_sqlite(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    try:
        connection = sqlite3.connect(str(path), timeout=1.0)
    except sqlite3.Error:
        return None
    connection.row_factory = sqlite3.Row
    return connection


def _duration_seconds(started_at: str, ended_at: str | None = None) -> int | None:
    started = _parse_iso_datetime(started_at)
    if started is None:
        return None
    ended = _parse_iso_datetime(ended_at or "") or datetime.now()
    return max(int((ended - started).total_seconds()), 0)


def _queue_job_view(row: sqlite3.Row, *, queue_position: int = 0) -> dict[str, Any]:
    created_at = normalize_spaces(str(row["created_at"] or ""))
    started_at = normalize_spaces(str(row["started_at"] or ""))
    finished_at = normalize_spaces(str(row["finished_at"] or ""))
    return {
        "jobId": int(row["id"]),
        "userOpenIdMasked": mask_user_openid(str(row["user_openid"] or "")),
        "jobKind": normalize_spaces(str(row["job_kind"] or "")),
        "mode": normalize_spaces(str(row["mode"] or "")),
        "status": normalize_spaces(str(row["status"] or "")),
        "createdAt": created_at,
        "startedAt": started_at,
        "finishedAt": finished_at,
        "runId": normalize_spaces(str(row["run_id"] or "")),
        "error": _trim_preview(str(row["error"] or ""), 140),
        "queuePosition": int(queue_position or 0),
        "waitSeconds": _duration_seconds(created_at, started_at or None),
        "runSeconds": _duration_seconds(started_at, finished_at or None),
    }


def _read_queue_snapshot(
    project_dir: Path,
    *,
    queue_limit: int,
    recent_job_limit: int,
) -> dict[str, Any]:
    db_path = job_db_path(project_dir)
    snapshot: dict[str, Any] = {
        "dbPath": str(db_path),
        "dbExists": db_path.exists(),
        "pendingCount": 0,
        "runningCount": 0,
        "pendingJobs": [],
        "runningJobs": [],
        "recentJobs": [],
        "error": "",
    }
    connection = _connect_readonly_sqlite(db_path)
    if connection is None:
        return snapshot
    try:
        pending_rows = connection.execute(
            """
            SELECT *
            FROM jobs
            WHERE status = 'pending'
            ORDER BY created_at, id
            LIMIT ?
            """,
            (max(int(queue_limit), 1),),
        ).fetchall()
        running_rows = connection.execute(
            """
            SELECT *
            FROM jobs
            WHERE status = 'running'
            ORDER BY COALESCE(started_at, created_at) DESC, id DESC
            LIMIT ?
            """,
            (max(int(queue_limit), 1),),
        ).fetchall()
        recent_rows = connection.execute(
            """
            SELECT *
            FROM jobs
            WHERE status IN ('completed', 'failed', 'canceled')
            ORDER BY COALESCE(finished_at, updated_at, created_at) DESC, id DESC
            LIMIT ?
            """,
            (max(int(recent_job_limit), 1),),
        ).fetchall()
        pending_count_row = connection.execute(
            "SELECT COUNT(*) AS count FROM jobs WHERE status = 'pending'"
        ).fetchone()
        running_count_row = connection.execute(
            "SELECT COUNT(*) AS count FROM jobs WHERE status = 'running'"
        ).fetchone()
        snapshot["pendingCount"] = int(pending_count_row["count"] if pending_count_row else 0)
        snapshot["runningCount"] = int(running_count_row["count"] if running_count_row else 0)
        snapshot["pendingJobs"] = [
            _queue_job_view(row, queue_position=index)
            for index, row in enumerate(pending_rows, start=1)
        ]
        snapshot["runningJobs"] = [_queue_job_view(row) for row in running_rows]
        snapshot["recentJobs"] = [_queue_job_view(row) for row in recent_rows]
        return snapshot
    except sqlite3.Error as exc:
        snapshot["error"] = str(exc)
        return snapshot
    finally:
        connection.close()


def _read_service_snapshot(project_dir: Path) -> dict[str, Any]:
    lock_payload = read_service_lock(project_dir) or {}
    status_payload = read_service_status(project_dir) or {}
    running = is_service_running(project_dir)
    run_id = normalize_spaces(str(status_payload.get("runId", "")))
    return {
        "lockPath": str(qq_bot_generate_service_state_root(project_dir) / "service.lock.json"),
        "statusPath": str(qq_bot_generate_service_state_root(project_dir) / "latest_status.json"),
        "eventsPath": str(_service_events_path(project_dir)),
        "stdoutPath": str(_service_stdout_path(project_dir)),
        "stderrPath": str(_service_stderr_path(project_dir)),
        "running": bool(running),
        "staleLock": bool(lock_payload) and not running,
        "pid": int(lock_payload.get("pid", 0) or 0),
        "startedAt": normalize_spaces(str(lock_payload.get("startedAt", ""))),
        "status": normalize_spaces(str(status_payload.get("status", ""))) or "unknown",
        "statusLabel": _status_label(str(status_payload.get("status", ""))),
        "stage": normalize_spaces(str(status_payload.get("stage", ""))),
        "stageLabel": normalize_stage_label(str(status_payload.get("stage", ""))),
        "updatedAt": normalize_spaces(str(status_payload.get("updatedAt", ""))),
        "statusAgeSeconds": _seconds_since(str(status_payload.get("updatedAt", ""))),
        "queuedCount": int(status_payload.get("queuedCount", 0) or 0),
        "queuePosition": int(status_payload.get("queuePosition", 0) or 0),
        "queueSize": int(status_payload.get("queueSize", 0) or 0),
        "runId": run_id,
        "runDetailRoute": _detail_route_for_run(run_id) if is_qq_bot_run_id(run_id) else "",
        "userOpenIdMasked": mask_user_openid(str(status_payload.get("userOpenId", ""))),
        "error": _trim_preview(str(status_payload.get("error", "")), 160),
        "generatedImagePath": normalize_spaces(str(status_payload.get("generatedImagePath", ""))),
        "publishPackagePath": normalize_spaces(str(status_payload.get("publishPackagePath", ""))),
        "failedRunRoot": normalize_spaces(str(status_payload.get("failedRunRoot", ""))),
    }


def _read_sampling_snapshot(project_dir: Path) -> dict[str, Any]:
    path = _social_sampling_health_path(project_dir)
    payload = _safe_read_json(path) or {}
    partitions = payload.get("partitions", {}) if isinstance(payload.get("partitions", {}), dict) else {}
    source_backoff = payload.get("sourceBackoff", {}) if isinstance(payload.get("sourceBackoff", {}), dict) else {}
    partition_backoff = (
        payload.get("partitionBackoff", {}) if isinstance(payload.get("partitionBackoff", {}), dict) else {}
    )

    top_failing = []
    for provider_key, item in partitions.items():
        if not isinstance(item, dict):
            continue
        top_failing.append(
            {
                "providerKey": provider_key,
                "providerZh": normalize_spaces(str(item.get("providerZh", ""))) or provider_key,
                "sourceZh": normalize_spaces(str(item.get("sourceZh", ""))),
                "consecutiveFailures": int(item.get("consecutiveFailures", 0) or 0),
                "failureCount": int(item.get("failureCount", 0) or 0),
                "lastError": _trim_preview(str(item.get("lastError", "")), 160),
                "lastSuccessAt": normalize_spaces(str(item.get("lastSuccessAt", ""))),
                "lastFailureAt": normalize_spaces(str(item.get("lastFailureAt", ""))),
            }
        )
    top_failing.sort(
        key=lambda item: (
            -int(item.get("consecutiveFailures", 0) or 0),
            -int(item.get("failureCount", 0) or 0),
            item.get("providerKey", ""),
        )
    )

    active_sources = []
    for source_key, item in source_backoff.items():
        if not isinstance(item, dict):
            continue
        active_sources.append(
            {
                "sourceKey": source_key,
                "blockedUntil": normalize_spaces(str(item.get("blockedUntil", ""))),
                "lastError": _trim_preview(str(item.get("lastError", "")), 160),
            }
        )

    active_partitions = []
    for provider_key, item in partition_backoff.items():
        if not isinstance(item, dict):
            continue
        active_partitions.append(
            {
                "providerKey": provider_key,
                "blockedUntil": normalize_spaces(str(item.get("blockedUntil", ""))),
                "lastError": _trim_preview(str(item.get("lastError", "")), 160),
            }
        )

    last_sample = payload.get("lastSample", {}) if isinstance(payload.get("lastSample", {}), dict) else {}
    return {
        "healthPath": str(path),
        "available": path.exists(),
        "updatedAt": normalize_spaces(str(payload.get("updatedAt", ""))),
        "lastSample": {
            "at": normalize_spaces(str(last_sample.get("at", ""))),
            "sourceZh": normalize_spaces(str(last_sample.get("sourceZh", ""))),
            "providerZh": normalize_spaces(str(last_sample.get("providerZh", ""))),
            "signalsZh": [
                _trim_preview(str(item), 180)
                for item in (last_sample.get("sampledSignalsZh", []) or [])
                if normalize_spaces(str(item))
            ],
        },
        "activeSourceBackoffs": active_sources,
        "activePartitionBackoffs": active_partitions,
        "topFailingPartitions": top_failing[:6],
    }


def _collect_recent_qq_run_ids(
    service_snapshot: dict[str, Any],
    queue_snapshot: dict[str, Any],
    events_snapshot: list[dict[str, Any]],
) -> list[str]:
    ordered_run_ids: list[str] = []
    seen: set[str] = set()

    def add(run_id: Any) -> None:
        normalized_run_id = normalize_spaces(str(run_id or ""))
        if not normalized_run_id or not is_qq_bot_run_id(normalized_run_id) or normalized_run_id in seen:
            return
        seen.add(normalized_run_id)
        ordered_run_ids.append(normalized_run_id)

    add(service_snapshot.get("runId"))
    for row in queue_snapshot.get("runningJobs", []) or []:
        if isinstance(row, dict):
            add(row.get("runId"))
    for row in events_snapshot:
        if isinstance(row, dict):
            add(row.get("runId"))
    for row in queue_snapshot.get("recentJobs", []) or []:
        if isinstance(row, dict):
            add(row.get("runId"))
    return ordered_run_ids


def _read_recent_runs(
    project_dir: Path,
    *,
    service_snapshot: dict[str, Any],
    queue_snapshot: dict[str, Any],
    events_snapshot: list[dict[str, Any]],
    run_limit: int,
) -> list[dict[str, Any]]:
    root = runs_root(project_dir)
    if not root.exists():
        return []

    candidate_run_ids = _collect_recent_qq_run_ids(service_snapshot, queue_snapshot, events_snapshot)
    seen = set(candidate_run_ids)
    if len(candidate_run_ids) < max(int(run_limit), 1):
        run_dirs = sorted(
            [path for path in root.iterdir() if path.is_dir() and is_qq_bot_run_id(path.name)],
            key=lambda path: path.name,
            reverse=True,
        )
        for run_dir in run_dirs:
            if run_dir.name in seen:
                continue
            seen.add(run_dir.name)
            candidate_run_ids.append(run_dir.name)
            if len(candidate_run_ids) >= max(int(run_limit), 1):
                break

    recent: list[dict[str, Any]] = []
    for run_id in candidate_run_ids:
        run_dir = root / run_id
        summary_path = run_dir / "output" / "run_summary.json"
        summary_payload = _safe_read_json(summary_path)
        if summary_payload is None:
            continue
        resolved_image_path = resolve_generated_image_artifact(project_dir, run_dir.name)
        receipts = summary_payload.get("publishReceipts", []) if isinstance(summary_payload.get("publishReceipts", []), list) else []
        first_receipt = receipts[0] if receipts and isinstance(receipts[0], dict) else {}
        recent.append(
            {
                "runId": normalize_spaces(str(summary_payload.get("runId", ""))) or run_dir.name,
                "runRoot": str(run_dir),
                "summaryPath": str(summary_path),
                "sceneDraftPremiseZh": _trim_preview(str(summary_payload.get("sceneDraftPremiseZh", "")), 80),
                "socialPostPreview": _trim_preview(str(summary_payload.get("socialPostText", "")), 120),
                "generatedImagePath": str(resolved_image_path) if resolved_image_path else "",
                "imageRoute": (
                    f"/artifacts/generated-image?runId={quote(run_dir.name, safe='')}"
                    if resolved_image_path
                    else ""
                ),
                "detailRoute": _detail_route_for_run(run_dir.name),
                "publishPackagePath": normalize_spaces(str(summary_payload.get("publishPackagePath", ""))),
                "published": bool(receipts),
                "publishedAt": normalize_spaces(str(first_receipt.get("publishedAt", ""))),
                "targetOpenIdMasked": mask_user_openid(str(first_receipt.get("targetOpenId", ""))),
                "publishStatus": normalize_spaces(str(first_receipt.get("status", ""))),
            }
        )
        if len(recent) >= max(int(run_limit), 1):
            break
    return recent


def resolve_generated_image_artifact(project_dir: Path, run_id: str) -> Path | None:
    return resolve_generic_generated_image_artifact(project_dir, run_id)


def resolve_dashboard_generated_image_artifact(project_dir: Path, run_id: str) -> Path | None:
    if not is_qq_bot_run_id(run_id):
        return None
    return resolve_generated_image_artifact(project_dir, run_id)


def build_run_detail_snapshot(project_dir: Path, run_id: str) -> dict[str, Any] | None:
    return build_generic_run_detail_snapshot(project_dir, run_id)


def build_dashboard_run_detail_snapshot(project_dir: Path, run_id: str) -> dict[str, Any] | None:
    if not is_qq_bot_run_id(run_id):
        return None
    detail = build_run_detail_snapshot(project_dir, run_id)
    if detail is None:
        return None
    return {
        **detail,
        "identity": _read_dashboard_identity(Path(project_dir).resolve()),
    }


def build_dashboard_snapshot(
    project_dir: Path,
    *,
    queue_limit: int = DEFAULT_QUEUE_LIMIT,
    recent_job_limit: int = DEFAULT_RECENT_JOB_LIMIT,
    event_limit: int = DEFAULT_EVENT_LIMIT,
    run_limit: int = DEFAULT_RUN_LIMIT,
    log_tail_lines: int = DEFAULT_LOG_TAIL_LINES,
) -> dict[str, Any]:
    project_dir = Path(project_dir).resolve()
    identity = _read_dashboard_identity(project_dir)
    service = _read_service_snapshot(project_dir)
    queue = _read_queue_snapshot(
        project_dir,
        queue_limit=max(int(queue_limit), 1),
        recent_job_limit=max(int(recent_job_limit), 1),
    )
    events = _tail_jsonl(_service_events_path(project_dir), max(int(event_limit), 1))
    return {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "projectDir": str(project_dir),
        "identity": identity,
        "service": service,
        "queue": queue,
        "events": events,
        "logs": {
            "stdoutPath": service["stdoutPath"],
            "stderrPath": service["stderrPath"],
            "stdoutTail": _tail_lines(_service_stdout_path(project_dir), max(int(log_tail_lines), 1)),
            "stderrTail": _tail_lines(_service_stderr_path(project_dir), max(int(log_tail_lines), 1)),
        },
        "sampling": _read_sampling_snapshot(project_dir),
        "recentRuns": _read_recent_runs(
            project_dir,
            service_snapshot=service,
            queue_snapshot=queue,
            events_snapshot=events,
            run_limit=max(int(run_limit), 1),
        ),
        "commands": {
            "dashboardStart": "python run_ops_dashboard.py",
            "dashboardStatus": "python run_ops_dashboard.py status",
            "dashboardStop": "python run_ops_dashboard.py stop",
            "dashboardRestart": "python run_ops_dashboard.py restart",
            "serviceStart": "python run_qq_bot_service.py start",
            "serviceStatus": "python run_qq_bot_service.py status",
            "serviceStop": "python run_qq_bot_service.py stop",
            "serviceRestart": "python run_qq_bot_service.py restart",
        },
    }
