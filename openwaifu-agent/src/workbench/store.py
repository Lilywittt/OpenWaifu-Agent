from __future__ import annotations

import csv
import json
import shutil
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from generation_slot import read_generation_slot
from io_utils import ensure_dir, normalize_spaces, write_json
from process_utils import is_process_alive
from review_favorites import (
    FAVORITE_KIND_PATH,
    FAVORITE_KIND_RUN,
    favorite_run_ids,
    favorite_selection_key,
    find_review_favorite,
    is_run_favorited,
    list_review_favorites,
    review_favorites_path,
    toggle_review_favorite,
)
from run_detail_store import build_run_detail_snapshot, build_run_detail_snapshot_from_path
from runtime_layout import runs_root, runtime_root
from sidecar_identity import read_bot_display_identity
from sidecar_control import sidecar_server_process_path, sidecar_state_root
from workbench.identity import WorkbenchViewer
from workbench.profile import PRIVATE_PROFILE, WorkbenchProfile

from test_pipeline import (
    END_STAGE_LABELS,
    SOURCE_ALLOWED_END_STAGES,
    SOURCE_KIND_HINTS,
    SOURCE_KIND_LABELS,
)


DEFAULT_HISTORY_LIMIT = 30
DEFAULT_CLEANUP_OLDER_THAN_DAYS = 14
INDEX_CSV_COLUMNS = [
    "recordedAt",
    "status",
    "deleted",
    "deletedAt",
    "label",
    "sourceKind",
    "sourceKindLabel",
    "endStage",
    "endStageLabel",
    "sceneDraftPremiseZh",
    "socialPostPreview",
    "positivePromptPreview",
    "generatedImagePath",
    "runId",
    "runRoot",
    "ownerId",
    "ownerDisplay",
    "summaryPath",
    "promptPackagePath",
    "creativePackagePath",
]
LEGACY_STATE_FILENAMES = (
    "latest_status.json",
    "history.jsonl",
    "last_request.json",
    "run_index.jsonl",
    "run_index.csv",
    "cleanup_report.json",
    "cleanup_report.csv",
)

WORKBENCH_STATE_DIRNAME = "workbench"


def _shared_workbench_state_root(project_dir: Path) -> Path:
    return runtime_root(project_dir) / "service_state" / "shared" / WORKBENCH_STATE_DIRNAME


def legacy_content_workbench_state_roots(project_dir: Path) -> tuple[Path, ...]:
    return (
        runtime_root(project_dir) / "service_state" / "studio" / "content_workbench",
        sidecar_state_root(project_dir, "content_workbench"),
        sidecar_state_root(project_dir, "public_workbench"),
    )


def content_workbench_state_root(project_dir: Path) -> Path:
    return _shared_workbench_state_root(project_dir)


def _status_path(project_dir: Path) -> Path:
    return content_workbench_state_root(project_dir) / "latest_status.json"


def _history_path(project_dir: Path) -> Path:
    return content_workbench_state_root(project_dir) / "history.jsonl"


def _last_request_path(project_dir: Path) -> Path:
    return content_workbench_state_root(project_dir) / "last_request.json"


def _last_requests_path(project_dir: Path) -> Path:
    return content_workbench_state_root(project_dir) / "last_requests.json"


def _active_worker_path(project_dir: Path) -> Path:
    return content_workbench_state_root(project_dir) / "active_worker.json"


def _active_request_path(project_dir: Path) -> Path:
    return content_workbench_state_root(project_dir) / "active_request.json"


def _stop_request_path(project_dir: Path) -> Path:
    return content_workbench_state_root(project_dir) / "stop_requested.json"


def _run_index_jsonl_path(project_dir: Path) -> Path:
    return content_workbench_state_root(project_dir) / "run_index.jsonl"


def _run_index_csv_path(project_dir: Path) -> Path:
    return content_workbench_state_root(project_dir) / "run_index.csv"


def _cleanup_report_json_path(project_dir: Path) -> Path:
    return content_workbench_state_root(project_dir) / "cleanup_report.json"


def _cleanup_report_csv_path(project_dir: Path) -> Path:
    return content_workbench_state_root(project_dir) / "cleanup_report.csv"


def workbench_inventory_paths(project_dir: Path) -> dict[str, str]:
    return {
        "stateRoot": str(content_workbench_state_root(project_dir)),
        "favoritesPath": str(review_favorites_path(project_dir)),
        "serverProcessPath": str(sidecar_server_process_path(project_dir, "content_workbench")),
        "generationSlotPath": str(runtime_root(project_dir) / "service_state" / "shared" / "generation_slot.json"),
        "activeWorkerPath": str(_active_worker_path(project_dir)),
        "activeRequestPath": str(_active_request_path(project_dir)),
        "stopRequestPath": str(_stop_request_path(project_dir)),
        "runIndexJsonlPath": str(_run_index_jsonl_path(project_dir)),
        "runIndexCsvPath": str(_run_index_csv_path(project_dir)),
        "cleanupReportJsonPath": str(_cleanup_report_json_path(project_dir)),
        "cleanupReportCsvPath": str(_cleanup_report_csv_path(project_dir)),
    }


def _safe_read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _safe_parse_datetime(raw_value: str) -> datetime | None:
    text = normalize_spaces(raw_value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _preview_text(value: Any, *, limit: int = 180) -> str:
    text = normalize_spaces(str(value or ""))
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 1)].rstrip() + "…"


def _append_jsonl_record(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


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
                records.append(
                    {
                        "status": "invalid",
                        "error": f"{path.name} 存在无法解析的记录。",
                        "recordedAt": "",
                    }
                )
                continue
            if isinstance(payload, dict):
                records.append(payload)
    return records


def migrate_legacy_content_workbench_state(project_dir: Path) -> bool:
    current_root = content_workbench_state_root(project_dir)
    migrated = False
    for legacy_root in legacy_content_workbench_state_roots(project_dir):
        if not legacy_root.exists():
            continue
        migrated_any_file = False
        for filename in LEGACY_STATE_FILENAMES:
            legacy_path = legacy_root / filename
            current_path = current_root / filename
            if not legacy_path.exists() or current_path.exists():
                continue
            ensure_dir(current_path.parent)
            shutil.copy2(legacy_path, current_path)
            migrated = True
            migrated_any_file = True
        for filename in LEGACY_STATE_FILENAMES:
            try:
                (legacy_root / filename).unlink()
            except (FileNotFoundError, OSError):
                continue
        if migrated_any_file and legacy_root.name == "content_workbench" and legacy_root.parent.name == "studio":
            shutil.rmtree(legacy_root, ignore_errors=True)
    return migrated


def _read_identity(project_dir: Path, profile: WorkbenchProfile) -> dict[str, str]:
    identity = read_bot_display_identity(project_dir, title_suffix=profile.title)
    return {
        "projectName": identity["projectName"],
        "botDisplayName": identity["botDisplayName"],
        "workbenchTitle": identity["title"],
    }


def _status_label(status: str) -> str:
    return {
        "idle": "空闲",
        "running": "运行中",
        "stopping": "停止中",
        "completed": "已完成",
        "deleted": "已删除",
        "failed": "失败",
        "interrupted": "已中断",
        "unknown": "未知",
    }.get(normalize_spaces(status), normalize_spaces(status) or "未知")


def read_workbench_status(project_dir: Path) -> dict[str, Any] | None:
    return _safe_read_json(_status_path(project_dir))


def write_workbench_status(project_dir: Path, payload: dict[str, Any]) -> Path:
    normalized_payload = {
        **payload,
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
    }
    path = _status_path(project_dir)
    write_json(path, normalized_payload)
    return path


def _normalize_owner_id(owner_id: str) -> str:
    return normalize_spaces(owner_id) or "private"


def _read_last_request_registry(project_dir: Path) -> dict[str, Any]:
    payload = _safe_read_json(_last_requests_path(project_dir))
    return payload if isinstance(payload, dict) else {}


def _write_last_request_registry(project_dir: Path, payload: dict[str, Any]) -> Path:
    path = _last_requests_path(project_dir)
    write_json(path, payload)
    return path


def read_last_request(project_dir: Path, *, owner_id: str = "") -> dict[str, Any] | None:
    owner_key = _normalize_owner_id(owner_id)
    registry = _read_last_request_registry(project_dir)
    payload = registry.get(owner_key)
    if isinstance(payload, dict) and payload:
        return payload
    if owner_key == "private":
        return _safe_read_json(_last_request_path(project_dir))
    return None


def write_last_request(project_dir: Path, payload: dict[str, Any], *, owner_id: str = "") -> Path:
    owner_key = _normalize_owner_id(owner_id)
    registry = _read_last_request_registry(project_dir)
    registry[owner_key] = payload
    _write_last_request_registry(project_dir, registry)
    path = _last_request_path(project_dir)
    if owner_key == "private":
        write_json(path, payload)
        return path
    return _last_requests_path(project_dir)


def read_active_request(project_dir: Path) -> dict[str, Any] | None:
    return _safe_read_json(_active_request_path(project_dir))


def write_active_request(project_dir: Path, payload: dict[str, Any]) -> Path:
    path = _active_request_path(project_dir)
    write_json(path, payload)
    return path


def clear_active_request(project_dir: Path) -> None:
    path = _active_request_path(project_dir)
    try:
        path.unlink()
    except (FileNotFoundError, OSError):
        return


def read_active_worker(project_dir: Path, *, cleanup_stale: bool = True) -> dict[str, Any] | None:
    payload = _safe_read_json(_active_worker_path(project_dir))
    if not payload:
        return None
    if is_process_alive(payload.get("pid")):
        return payload
    if cleanup_stale:
        clear_active_worker(project_dir)
    return None


def write_active_worker(project_dir: Path, payload: dict[str, Any]) -> Path:
    path = _active_worker_path(project_dir)
    write_json(path, payload)
    return path


def clear_active_worker(project_dir: Path) -> None:
    path = _active_worker_path(project_dir)
    try:
        path.unlink()
    except (FileNotFoundError, OSError):
        return


def request_workbench_stop(project_dir: Path) -> Path:
    path = _stop_request_path(project_dir)
    write_json(path, {"requestedAt": datetime.now().isoformat(timespec="seconds")})
    return path


def is_workbench_stop_requested(project_dir: Path) -> bool:
    return _stop_request_path(project_dir).exists()


def clear_workbench_stop_request(project_dir: Path) -> None:
    path = _stop_request_path(project_dir)
    try:
        path.unlink()
    except (FileNotFoundError, OSError):
        return


def append_history_record(project_dir: Path, payload: dict[str, Any]) -> None:
    record = {
        **payload,
        "recordedAt": datetime.now().isoformat(timespec="seconds"),
    }
    _append_jsonl_record(_history_path(project_dir), record)


def record_terminal_workbench_payload(project_dir: Path, payload: dict[str, Any]) -> None:
    write_workbench_status(project_dir, payload)
    append_history_record(project_dir, payload)
    append_run_index_record(project_dir, payload)


def normalize_stale_workbench_status(project_dir: Path) -> bool:
    payload = read_workbench_status(project_dir)
    if not payload:
        return False
    status = normalize_spaces(str(payload.get("status", "")))
    if status not in {"running", "stopping"}:
        return False
    if read_active_worker(project_dir, cleanup_stale=True) is not None:
        return False
    error = normalize_spaces(str(payload.get("error", ""))) or "上一轮测试进程已退出，测试未完成。"
    write_workbench_status(
        project_dir,
        {
            **payload,
            "status": "interrupted",
            "stage": "",
            "error": error,
            "finishedAt": datetime.now().isoformat(timespec="seconds"),
        },
    )
    clear_active_request(project_dir)
    clear_workbench_stop_request(project_dir)
    return True


def reconcile_workbench_runtime_state(project_dir: Path) -> bool:
    project_dir = Path(project_dir).resolve()
    active_worker = read_active_worker(project_dir, cleanup_stale=True)
    status_payload = read_workbench_status(project_dir) or {}
    status = normalize_spaces(str(status_payload.get("status", "")))
    if active_worker is not None:
        if status in {"running", "stopping"}:
            return False
        request = read_active_request(project_dir) or active_worker.get("request") or {}
        write_workbench_status(
            project_dir,
            {
                **status_payload,
                "status": "running",
                "stage": (
                    "测试运行中"
                    if status in {"completed", "failed", "interrupted", "deleted"}
                    else normalize_spaces(str(status_payload.get("stage", ""))) or "测试运行中"
                ),
                "request": request if isinstance(request, dict) else {},
                "startedAt": normalize_spaces(str(status_payload.get("startedAt", "")))
                or normalize_spaces(str(active_worker.get("startedAt", ""))),
                "error": "",
            },
        )
        return True
    return normalize_stale_workbench_status(project_dir)


def finalize_workbench_runtime(project_dir: Path) -> None:
    clear_active_worker(project_dir)
    clear_active_request(project_dir)
    clear_workbench_stop_request(project_dir)


def _tail_history(project_dir: Path, *, limit: int) -> list[dict[str, Any]]:
    rows: deque[dict[str, Any]] = deque(maxlen=max(int(limit), 1))
    for payload in _read_jsonl_records(_history_path(project_dir)):
        rows.append(payload)
    return list(reversed(list(rows)))


def _time_rank(value: str) -> int:
    digits = "".join(ch for ch in normalize_spaces(value) if ch.isdigit())
    return int(digits) if digits else 0


def _history_sort_rank(item: dict[str, Any]) -> tuple[int, int]:
    deleted = 1 if bool(item.get("deleted", False)) else 0
    running = 0 if normalize_spaces(str(item.get("status", ""))) in {"running", "stopping"} else 1
    timestamp = (
        normalize_spaces(str(item.get("deletedAt", "")))
        or normalize_spaces(str(item.get("recordedAt", "")))
        or normalize_spaces(str(item.get("finishedAt", "")))
        or normalize_spaces(str(item.get("startedAt", "")))
    )
    return (deleted, running, -_time_rank(timestamp))


def _build_current_history_candidate(status_payload: dict[str, Any]) -> dict[str, Any] | None:
    request = status_payload.get("request", {}) if isinstance(status_payload.get("request"), dict) else {}
    run_id = normalize_spaces(str(status_payload.get("runId", "")))
    run_root = normalize_spaces(str(status_payload.get("runRoot", "")))
    status = normalize_spaces(str(status_payload.get("status", "")))
    if status not in {"running", "stopping"}:
        return None
    recorded_at = (
        normalize_spaces(str(status_payload.get("startedAt", "")))
        or normalize_spaces(str(status_payload.get("updatedAt", "")))
        or datetime.now().isoformat(timespec="seconds")
    )
    return {
        "selectionKey": run_id or "__active__",
        "recordedAt": recorded_at,
        "startedAt": normalize_spaces(str(status_payload.get("startedAt", ""))) or recorded_at,
        "finishedAt": normalize_spaces(str(status_payload.get("finishedAt", ""))),
        "status": status,
        "deleted": False,
        "deletedAt": "",
        "runId": run_id,
        "runRoot": run_root,
        "summaryPath": normalize_spaces(str(status_payload.get("summaryPath", ""))),
        "label": normalize_spaces(str(request.get("label", ""))),
        "sourceKind": normalize_spaces(str(request.get("sourceKind", ""))),
        "endStage": normalize_spaces(str(request.get("endStage", ""))),
        "ownerId": normalize_spaces(str(request.get("ownerId", ""))),
        "ownerDisplay": normalize_spaces(str(request.get("ownerDisplay", ""))),
        "sceneDraftPremiseZh": normalize_spaces(str(status_payload.get("sceneDraftPremiseZh", ""))),
        "error": normalize_spaces(str(status_payload.get("error", ""))),
    }


def _summarize_request_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    summary: dict[str, Any] = {}
    for key in ("sourceKind", "endStage", "label", "requestId", "sourcePath", "sceneDraftPremiseZh"):
        value = payload.get(key)
        if value in (None, ""):
            continue
        summary[key] = value
    return summary


def _normalize_history_filter(value: str) -> str:
    normalized = normalize_spaces(value).lower()
    if normalized in {"all", "favorites", "deleted"}:
        return normalized
    return "active"


def _normalize_record_owner(item: dict[str, Any]) -> str:
    request = item.get("request", {}) if isinstance(item.get("request"), dict) else {}
    owner_id = normalize_spaces(str(item.get("ownerId", ""))) or normalize_spaces(str(request.get("ownerId", "")))
    return owner_id or "private"


def _viewer_can_access_record(
    item: dict[str, Any],
    *,
    viewer: WorkbenchViewer,
    profile: WorkbenchProfile,
) -> bool:
    if not profile.public or profile.allow_global_history:
        return True
    return _normalize_record_owner(item) == _normalize_owner_id(viewer.owner_id)


def _public_busy_status_payload(
    status_payload: dict[str, Any],
    *,
    slot_holder: dict[str, Any] | None,
) -> dict[str, Any]:
    status = normalize_spaces(str(status_payload.get("status", "")))
    if status in {"running", "stopping"}:
        return {
            **status_payload,
            "stage": "当前有其他体验任务正在运行",
            "runId": "",
            "runRoot": "",
            "error": "",
            "request": {},
        }
    if slot_holder:
        return {
            **status_payload,
            "stage": "当前执行位正在被占用",
            "runId": "",
            "runRoot": "",
            "error": "",
            "request": {},
        }
    return {
        **status_payload,
        "request": {},
    }


def _filter_history_records(records: list[dict[str, Any]], history_filter: str) -> list[dict[str, Any]]:
    normalized_filter = _normalize_history_filter(history_filter)
    if normalized_filter == "deleted":
        return [item for item in records if bool(item.get("deleted", False))]
    if normalized_filter == "all":
        return list(records)
    return [item for item in records if not bool(item.get("deleted", False))]


def _decorate_favorite_view_item(item: dict[str, Any], favorite: dict[str, Any] | None) -> dict[str, Any]:
    favorite_payload = favorite or {}
    item["favorite"] = bool(favorite_payload)
    item["favoriteKind"] = normalize_spaces(str(favorite_payload.get("kind", "")))
    item["favoriteTarget"] = normalize_spaces(str(favorite_payload.get("target", "")))
    item["favoriteSavedAt"] = normalize_spaces(str(favorite_payload.get("savedAt", "")))
    item["reviewPath"] = normalize_spaces(str(favorite_payload.get("path", "")))
    return item


def _build_favorite_view_item(
    project_dir: Path,
    favorite: dict[str, Any],
    run_index_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    kind = normalize_spaces(str(favorite.get("kind", ""))).lower()
    if kind == FAVORITE_KIND_RUN:
        run_id = normalize_spaces(str(favorite.get("runId", ""))) or normalize_spaces(str(favorite.get("target", "")))
        indexed_record = dict(run_index_map.get(run_id, {}))
        run_root_text = normalize_spaces(str(favorite.get("runRoot", ""))) or normalize_spaces(str(indexed_record.get("runRoot", "")))
        run_root_path = Path(run_root_text) if run_root_text else None
        run_exists = bool(run_root_path and run_root_path.exists())
        payload = {
            **indexed_record,
            "selectionKey": favorite_selection_key(FAVORITE_KIND_RUN, run_id),
            "recordedAt": normalize_spaces(str(favorite.get("savedAt", ""))) or normalize_spaces(str(indexed_record.get("recordedAt", ""))),
            "runId": run_id,
            "runRoot": run_root_text,
            "label": normalize_spaces(str(favorite.get("label", ""))) or normalize_spaces(str(indexed_record.get("label", ""))),
            "sourceKind": normalize_spaces(str(favorite.get("sourceKind", ""))) or normalize_spaces(str(indexed_record.get("sourceKind", ""))),
            "endStage": normalize_spaces(str(favorite.get("endStage", ""))) or normalize_spaces(str(indexed_record.get("endStage", ""))),
            "sceneDraftPremiseZh": normalize_spaces(str(favorite.get("sceneDraftPremiseZh", "")))
            or normalize_spaces(str(indexed_record.get("sceneDraftPremiseZh", "")))
            or normalize_spaces(str(favorite.get("title", ""))),
            "status": normalize_spaces(str(indexed_record.get("status", ""))) or ("completed" if run_exists else "missing"),
            "statusLabel": normalize_spaces(str(indexed_record.get("statusLabel", ""))) or ("已收藏" if run_exists else "路径失效"),
            "deleted": bool(indexed_record.get("deleted", False)),
            "deletedAt": normalize_spaces(str(indexed_record.get("deletedAt", ""))),
            "summaryPath": normalize_spaces(str(indexed_record.get("summaryPath", ""))) if run_exists else "",
            "imageRoute": normalize_spaces(str(indexed_record.get("imageRoute", ""))) if run_exists else "",
            "error": normalize_spaces(str(indexed_record.get("error", ""))) or ("" if run_exists else "收藏的 run 目录当前不可用。"),
        }
        view_item = _build_history_view_item(project_dir, payload)
        if not run_exists:
            view_item["status"] = "missing"
            view_item["statusLabel"] = "路径失效"
            view_item["error"] = "收藏的 run 目录当前不可用。"
            view_item["imageRoute"] = ""
        return _decorate_favorite_view_item(view_item, favorite)

    path_text = normalize_spaces(str(favorite.get("path", ""))) or normalize_spaces(str(favorite.get("target", "")))
    detail = build_run_detail_snapshot_from_path(project_dir, path_text)
    if detail is not None:
        payload = {
            "selectionKey": favorite_selection_key(FAVORITE_KIND_PATH, path_text),
            "recordedAt": normalize_spaces(str(favorite.get("savedAt", ""))),
            "runId": normalize_spaces(str(detail.get("runId", ""))),
            "runRoot": normalize_spaces(str(detail.get("runRoot", ""))),
            "label": normalize_spaces(str(favorite.get("label", ""))),
            "sourceKind": normalize_spaces(str(favorite.get("sourceKind", ""))),
            "endStage": normalize_spaces(str(favorite.get("endStage", ""))),
            "sceneDraftPremiseZh": normalize_spaces(str(favorite.get("sceneDraftPremiseZh", "")))
            or normalize_spaces(str(detail.get("detailTitle", "")))
            or normalize_spaces(str(favorite.get("title", ""))),
            "status": "saved",
            "statusLabel": "已收藏",
            "deleted": False,
            "summaryPath": normalize_spaces(str(detail.get("summaryPath", ""))),
            "imageRoute": normalize_spaces(str(detail.get("imageRoute", ""))),
            "error": "",
        }
        view_item = _build_history_view_item(project_dir, payload)
        if normalize_spaces(str(payload.get("imageRoute", ""))):
            view_item["imageRoute"] = normalize_spaces(str(payload.get("imageRoute", "")))
        return _decorate_favorite_view_item(view_item, favorite)

    payload = {
        "selectionKey": favorite_selection_key(FAVORITE_KIND_PATH, path_text),
        "recordedAt": normalize_spaces(str(favorite.get("savedAt", ""))),
        "displayTime": normalize_spaces(str(favorite.get("savedAt", ""))),
        "runId": normalize_spaces(str(favorite.get("runId", ""))),
        "runRoot": normalize_spaces(str(favorite.get("runRoot", ""))),
        "label": normalize_spaces(str(favorite.get("label", ""))),
        "sourceKind": normalize_spaces(str(favorite.get("sourceKind", ""))),
        "endStage": normalize_spaces(str(favorite.get("endStage", ""))),
        "sceneDraftPremiseZh": normalize_spaces(str(favorite.get("sceneDraftPremiseZh", "")))
        or normalize_spaces(str(favorite.get("title", ""))),
        "status": "missing",
        "statusLabel": "路径失效",
        "deleted": False,
        "summaryPath": "",
        "error": "收藏路径当前不可用。",
    }
    return _decorate_favorite_view_item(_build_history_view_item(project_dir, payload), favorite)


def _build_filtered_history_records(
    project_dir: Path,
    *,
    limit: int,
    history_filter: str,
    viewer: WorkbenchViewer,
    profile: WorkbenchProfile,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, Any]]:
    records = [dict(record) for record in _read_run_index_records(project_dir)]
    records = [record for record in records if _viewer_can_access_record(record, viewer=viewer, profile=profile)]
    records.sort(key=_history_sort_rank)
    normalized_filter = _normalize_history_filter(history_filter)
    favorites = list_review_favorites(project_dir) if profile.allow_favorites else []
    run_index_map = {
        normalize_spaces(str(record.get("runId", ""))): record
        for record in records
        if normalize_spaces(str(record.get("runId", "")))
    }
    stats = {
        "total": len(records),
        "active": sum(1 for item in records if not bool(item.get("deleted", False))),
        "deleted": sum(1 for item in records if bool(item.get("deleted", False))),
        "favorites": len(favorites),
    }
    bounded_limit = max(int(limit), 1)
    if normalized_filter == "favorites":
        filtered_items = [_build_favorite_view_item(project_dir, favorite, run_index_map) for favorite in favorites]
        filtered_items = [
            item
            for item in filtered_items
            if _viewer_can_access_record(item, viewer=viewer, profile=profile)
        ]
        visible = filtered_items[:bounded_limit]
        total_filtered = len(filtered_items)
    else:
        filtered_records = _filter_history_records(records, normalized_filter)
        visible = []
        for item in filtered_records[:bounded_limit]:
            view_item = _build_history_view_item(project_dir, item)
            selection_key = normalize_spaces(str(view_item.get("selectionKey", "")))
            visible.append(_decorate_favorite_view_item(view_item, find_review_favorite(project_dir, selection_key=selection_key)))
        total_filtered = len(filtered_records)
    page = {
        "filter": normalized_filter,
        "limit": bounded_limit,
        "loaded": len(visible),
        "totalFiltered": total_filtered,
        "hasMore": total_filtered > len(visible),
    }
    return (visible, stats, page)


def _build_current_run_item(
    project_dir: Path,
    status_payload: dict[str, Any],
    *,
    viewer: WorkbenchViewer,
    profile: WorkbenchProfile,
) -> dict[str, Any] | None:
    candidate = _build_current_history_candidate(status_payload)
    if candidate is None:
        return None
    if not _viewer_can_access_record(candidate, viewer=viewer, profile=profile):
        return None
    view_item = _build_history_view_item(project_dir, candidate)
    selection_key = normalize_spaces(str(view_item.get("selectionKey", "")))
    return _decorate_favorite_view_item(view_item, find_review_favorite(project_dir, selection_key=selection_key))


def _build_source_kind_config(profile: WorkbenchProfile) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for source_kind, label in SOURCE_KIND_LABELS.items():
        if not profile.allows_all_source_kinds and source_kind not in profile.allowed_source_kinds:
            continue
        allowed_stage_ids = list(SOURCE_ALLOWED_END_STAGES[source_kind])
        options.append(
            {
                "id": source_kind,
                "label": label,
                "hint": SOURCE_KIND_HINTS.get(source_kind, ""),
                "allowedEndStages": [
                    {"id": stage_id, "label": END_STAGE_LABELS.get(stage_id, stage_id)}
                    for stage_id in allowed_stage_ids
                ],
            }
        )
    return options


def _build_history_view_item(project_dir: Path, item: dict[str, Any]) -> dict[str, Any]:
    request = item.get("request", {}) if isinstance(item.get("request"), dict) else {}
    run_id = normalize_spaces(str(item.get("runId", "")))
    run_root = normalize_spaces(str(item.get("runRoot", "")))
    scene_premise = normalize_spaces(str(item.get("sceneDraftPremiseZh", "")))
    error = normalize_spaces(str(item.get("error", "")))
    source_kind = normalize_spaces(str(item.get("sourceKind", ""))) or normalize_spaces(str(request.get("sourceKind", "")))
    end_stage = normalize_spaces(str(item.get("endStage", ""))) or normalize_spaces(str(request.get("endStage", "")))
    label = normalize_spaces(str(item.get("label", ""))) or normalize_spaces(str(request.get("label", "")))
    deleted = bool(item.get("deleted", False))
    recorded_at = normalize_spaces(str(item.get("recordedAt", ""))) or normalize_spaces(str(item.get("finishedAt", ""))) or normalize_spaces(str(item.get("startedAt", "")))
    display_time = normalize_spaces(str(item.get("displayTime", ""))) or (normalize_spaces(str(item.get("deletedAt", ""))) if deleted else recorded_at)
    image_route = normalize_spaces(str(item.get("imageRoute", "")))
    if not image_route and run_id and not deleted:
        image_route = f"/artifacts/generated-image?runId={run_id}"
    status_label = normalize_spaces(str(item.get("statusLabel", ""))) or _status_label(str(item.get("status", "")))
    source_kind_label = normalize_spaces(str(item.get("sourceKindLabel", ""))) or SOURCE_KIND_LABELS.get(
        source_kind,
        source_kind,
    )
    end_stage_label = normalize_spaces(str(item.get("endStageLabel", ""))) or END_STAGE_LABELS.get(
        end_stage,
        end_stage,
    )
    return {
        "selectionKey": normalize_spaces(str(item.get("selectionKey", ""))) or run_id,
        "recordedAt": recorded_at,
        "displayTime": display_time,
        "status": normalize_spaces(str(item.get("status", ""))),
        "statusLabel": status_label,
        "deleted": deleted,
        "deletedAt": normalize_spaces(str(item.get("deletedAt", ""))),
        "runId": run_id,
        "runRoot": run_root,
        "label": label,
        "sourceKind": source_kind,
        "sourceKindLabel": source_kind_label,
        "endStage": end_stage,
        "endStageLabel": end_stage_label,
        "sceneDraftPremiseZh": scene_premise,
        "error": error,
        "summaryPath": normalize_spaces(str(item.get("summaryPath", ""))),
        "imageRoute": image_route,
        "favorite": bool(item.get("favorite", False)),
        "favoriteKind": normalize_spaces(str(item.get("favoriteKind", ""))),
        "favoriteTarget": normalize_spaces(str(item.get("favoriteTarget", ""))),
        "favoriteSavedAt": normalize_spaces(str(item.get("favoriteSavedAt", ""))),
        "reviewPath": normalize_spaces(str(item.get("reviewPath", ""))),
        "ownerId": _normalize_record_owner(item),
        "ownerDisplay": normalize_spaces(str(item.get("ownerDisplay", "")))
        or normalize_spaces(str(request.get("ownerDisplay", ""))),
    }


def _summary_path_from_payload(project_dir: Path, payload: dict[str, Any]) -> Path | None:
    summary_path_text = normalize_spaces(str(payload.get("summaryPath", "")))
    if summary_path_text:
        return Path(summary_path_text)
    run_root_text = normalize_spaces(str(payload.get("runRoot", "")))
    run_id = normalize_spaces(str(payload.get("runId", "")))
    if run_root_text:
        return Path(run_root_text) / "output" / "run_summary.json"
    if run_id:
        return runs_root(project_dir) / run_id / "output" / "run_summary.json"
    return None


def _build_run_index_record(project_dir: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    request = payload.get("request", {}) if isinstance(payload.get("request"), dict) else {}
    run_id = normalize_spaces(str(payload.get("runId", "")))
    run_root = normalize_spaces(str(payload.get("runRoot", "")))
    if not run_id and not run_root:
        return None

    summary_path = _summary_path_from_payload(project_dir, payload)
    summary_payload = _safe_read_json(summary_path) if summary_path is not None else None
    summary_payload = summary_payload or {}
    summary_run_root = Path(run_root) if run_root else (runs_root(project_dir) / run_id if run_id else None)
    summary_path_text = str(summary_path) if summary_path is not None else ""

    return {
        "recordedAt": datetime.now().isoformat(timespec="seconds"),
        "startedAt": normalize_spaces(str(payload.get("startedAt", ""))),
        "finishedAt": normalize_spaces(str(payload.get("finishedAt", ""))),
        "status": normalize_spaces(str(payload.get("status", ""))),
        "deleted": False,
        "deletedAt": "",
        "runId": run_id,
        "runRoot": str(summary_run_root) if summary_run_root is not None else run_root,
        "ownerId": normalize_spaces(str(request.get("ownerId", ""))) or "private",
        "ownerDisplay": normalize_spaces(str(request.get("ownerDisplay", ""))),
        "summaryPath": summary_path_text,
        "label": normalize_spaces(str(request.get("label", ""))),
        "sourceKind": normalize_spaces(str(request.get("sourceKind", ""))),
        "sourceKindLabel": SOURCE_KIND_LABELS.get(
            normalize_spaces(str(request.get("sourceKind", ""))),
            normalize_spaces(str(request.get("sourceKind", ""))),
        ),
        "endStage": normalize_spaces(str(request.get("endStage", ""))),
        "endStageLabel": END_STAGE_LABELS.get(
            normalize_spaces(str(request.get("endStage", ""))),
            normalize_spaces(str(request.get("endStage", ""))),
        ),
        "sceneDraftPremiseZh": normalize_spaces(
            str(payload.get("sceneDraftPremiseZh", "") or summary_payload.get("sceneDraftPremiseZh", ""))
        ),
        "socialPostPreview": _preview_text(summary_payload.get("socialPostText", "")),
        "positivePromptPreview": _preview_text(summary_payload.get("positivePromptText", "")),
        "generatedImagePath": normalize_spaces(str(summary_payload.get("generatedImagePath", ""))),
        "promptPackagePath": normalize_spaces(str(summary_payload.get("promptPackagePath", ""))),
        "creativePackagePath": normalize_spaces(str(summary_payload.get("creativePackagePath", ""))),
    }


def _rewrite_index_csv(project_dir: Path) -> None:
    records = _read_jsonl_records(_run_index_jsonl_path(project_dir))
    target_path = _run_index_csv_path(project_dir)
    ensure_dir(target_path.parent)
    with target_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INDEX_CSV_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow({column: record.get(column, "") for column in INDEX_CSV_COLUMNS})


def append_run_index_record(project_dir: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    record = _build_run_index_record(project_dir, payload)
    if record is None:
        return None
    _append_jsonl_record(_run_index_jsonl_path(project_dir), record)
    _rewrite_index_csv(project_dir)
    return record


def _read_run_index_records(project_dir: Path) -> list[dict[str, Any]]:
    return _read_jsonl_records(_run_index_jsonl_path(project_dir))


def can_access_workbench_run(
    project_dir: Path,
    run_id: str,
    *,
    viewer: WorkbenchViewer,
    profile: WorkbenchProfile,
) -> bool:
    normalized_run_id = normalize_spaces(run_id)
    if not normalized_run_id:
        return False
    if not profile.public or profile.allow_global_history:
        return True
    for record in reversed(_read_run_index_records(project_dir)):
        if normalize_spaces(str(record.get("runId", ""))) != normalized_run_id:
            continue
        return _viewer_can_access_record(record, viewer=viewer, profile=profile)
    status_payload = read_workbench_status(project_dir) or {}
    if normalize_spaces(str(status_payload.get("runId", ""))) != normalized_run_id:
        return False
    return _viewer_can_access_record(status_payload, viewer=viewer, profile=profile)


def _write_run_index_records(project_dir: Path, records: list[dict[str, Any]]) -> None:
    target_path = _run_index_jsonl_path(project_dir)
    ensure_dir(target_path.parent)
    with target_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    _rewrite_index_csv(project_dir)


def _safe_run_root(project_dir: Path, run_id: str) -> Path:
    normalized_run_id = normalize_spaces(run_id)
    if not normalized_run_id:
        raise RuntimeError("runId 不能为空。")
    runs_dir = runs_root(project_dir).resolve()
    candidate = (runs_dir / normalized_run_id).resolve()
    if candidate.parent != runs_dir:
        raise RuntimeError("runId 非法，拒绝删除。")
    return candidate


def delete_workbench_run(project_dir: Path, run_id: str) -> dict[str, Any]:
    project_dir = Path(project_dir).resolve()
    normalized_run_id = normalize_spaces(run_id)
    target_root = _safe_run_root(project_dir, normalized_run_id)
    if is_run_favorited(project_dir, normalized_run_id):
        raise RuntimeError("当前目录已加入收藏，请先取消收藏再删除。")
    status_payload = read_workbench_status(project_dir) or {}
    status = normalize_spaces(str(status_payload.get("status", "")))
    active_run_id = normalize_spaces(str(status_payload.get("runId", "")))
    if status in {"running", "stopping"} and active_run_id == normalized_run_id:
        raise RuntimeError("当前这轮测试仍在运行，不能删除它的目录。")
    if not target_root.exists():
        raise RuntimeError(f"未找到 run 目录：{normalized_run_id}")
    if not target_root.is_dir():
        raise RuntimeError(f"目标不是目录：{normalized_run_id}")

    deleted_at = datetime.now().isoformat(timespec="seconds")
    index_records = _read_run_index_records(project_dir)
    latest_record = next(
        (
            record
            for record in reversed(index_records)
            if normalize_spaces(str(record.get("runId", ""))) == normalized_run_id
        ),
        {},
    )
    shutil.rmtree(target_root)

    for record in index_records:
        if normalize_spaces(str(record.get("runId", ""))) != normalized_run_id:
            continue
        record["deleted"] = True
        record["deletedAt"] = deleted_at
    if index_records:
        _write_run_index_records(project_dir, index_records)

    delete_history_payload = {
        "status": "deleted",
        "runId": normalized_run_id,
        "runRoot": str(target_root),
        "finishedAt": deleted_at,
        "deleted": True,
        "deletedAt": deleted_at,
        "sceneDraftPremiseZh": normalize_spaces(str(latest_record.get("sceneDraftPremiseZh", ""))),
        "error": "",
        "request": {
            "label": normalize_spaces(str(latest_record.get("label", ""))),
            "sourceKind": normalize_spaces(str(latest_record.get("sourceKind", ""))),
            "endStage": normalize_spaces(str(latest_record.get("endStage", ""))),
        },
        "summaryPath": normalize_spaces(str(latest_record.get("summaryPath", ""))),
    }
    append_history_record(project_dir, delete_history_payload)
    return {
        "runId": normalized_run_id,
        "runRoot": str(target_root),
        "deletedAt": deleted_at,
    }


def generate_cleanup_report(
    project_dir: Path,
    *,
    older_than_days: int = DEFAULT_CLEANUP_OLDER_THAN_DAYS,
    statuses: tuple[str, ...] = ("completed", "failed", "interrupted"),
) -> dict[str, Any]:
    threshold = datetime.now() - timedelta(days=max(int(older_than_days), 0))
    normalized_statuses = tuple(normalize_spaces(status) for status in statuses if normalize_spaces(status))
    protected_run_ids = favorite_run_ids(project_dir)
    candidates: list[dict[str, Any]] = []

    for record in _read_run_index_records(project_dir):
        if bool(record.get("deleted", False)):
            continue
        if normalize_spaces(str(record.get("runId", ""))) in protected_run_ids:
            continue
        finished_at = _safe_parse_datetime(str(record.get("finishedAt", "")))
        recorded_at = _safe_parse_datetime(str(record.get("recordedAt", "")))
        effective_time = finished_at or recorded_at
        if effective_time is None or effective_time > threshold:
            continue
        if normalized_statuses and normalize_spaces(str(record.get("status", ""))) not in normalized_statuses:
            continue

        run_root = Path(str(record.get("runRoot", ""))) if normalize_spaces(str(record.get("runRoot", ""))) else None
        image_path_text = normalize_spaces(str(record.get("generatedImagePath", "")))
        image_path = Path(image_path_text) if image_path_text else None
        candidates.append(
            {
                **record,
                "runExists": bool(run_root and run_root.exists()),
                "imageExists": bool(image_path and image_path.exists()),
                "ageDays": max(int((datetime.now() - effective_time).total_seconds() // 86400), 0),
            }
        )

    report = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "olderThanDays": max(int(older_than_days), 0),
        "statuses": list(normalized_statuses),
        "candidateCount": len(candidates),
        "indexJsonlPath": str(_run_index_jsonl_path(project_dir)),
        "indexCsvPath": str(_run_index_csv_path(project_dir)),
        "candidates": candidates,
    }
    write_json(_cleanup_report_json_path(project_dir), report)
    with _cleanup_report_csv_path(project_dir).open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = [
            "ageDays",
            "status",
            "label",
            "sourceKind",
            "endStage",
            "sceneDraftPremiseZh",
            "runExists",
            "imageExists",
            "generatedImagePath",
            "runId",
            "runRoot",
            "summaryPath",
            "recordedAt",
            "finishedAt",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for candidate in candidates:
            writer.writerow({field: candidate.get(field, "") for field in fieldnames})
    return report


def toggle_workbench_favorite(project_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return toggle_review_favorite(Path(project_dir).resolve(), payload)


def _build_inventory_payload(project_dir: Path) -> dict[str, Any]:
    paths = workbench_inventory_paths(project_dir)
    record_count = len(_read_run_index_records(project_dir))
    return {
        **paths,
        "runIndexRecordCount": record_count,
        "cleanupCommand": (
            "python run_content_workbench.py cleanup-report "
            f"--older-than-days {DEFAULT_CLEANUP_OLDER_THAN_DAYS}"
        ),
    }


def build_content_workbench_snapshot(
    project_dir: Path,
    *,
    selected_run_id: str = "",
    history_filter: str = "active",
    history_limit: int = DEFAULT_HISTORY_LIMIT,
    viewer: WorkbenchViewer | None = None,
    profile: WorkbenchProfile = PRIVATE_PROFILE,
) -> dict[str, Any]:
    project_dir = Path(project_dir).resolve()
    effective_viewer = viewer or WorkbenchViewer(
        owner_id="private",
        display_name="私有工作台",
        email="",
        authenticated=True,
        public=False,
    )
    normalized_history_filter = _normalize_history_filter(history_filter)
    if normalized_history_filter == "favorites" and not profile.allow_favorites:
        normalized_history_filter = "active"
    if normalized_history_filter == "deleted" and not profile.allow_deleted_history:
        normalized_history_filter = "active"
    identity = _read_identity(project_dir, profile)
    status_payload = read_workbench_status(project_dir) or {}
    slot_holder = read_generation_slot(project_dir, cleanup_stale=True)
    viewer_controls_current_task = _viewer_can_access_record(status_payload, viewer=effective_viewer, profile=profile)
    if profile.public and not viewer_controls_current_task:
        visible_status_payload = _public_busy_status_payload(status_payload, slot_holder=slot_holder)
    else:
        visible_status_payload = status_payload
    current_run_item = _build_current_run_item(project_dir, visible_status_payload, viewer=effective_viewer, profile=profile)
    history_records, history_stats, history_page = _build_filtered_history_records(
        project_dir,
        limit=history_limit,
        history_filter=normalized_history_filter,
        viewer=effective_viewer,
        profile=profile,
    )
    last_request = read_last_request(project_dir, owner_id=effective_viewer.owner_id) or {}

    status = normalize_spaces(str(visible_status_payload.get("status", ""))) or "idle"
    run_id_from_status = normalize_spaces(str(visible_status_payload.get("runId", "")))
    active_worker = read_active_worker(project_dir, cleanup_stale=True)
    try:
        status_worker_pid = int(visible_status_payload.get("workerPid", 0) or 0)
    except (TypeError, ValueError):
        status_worker_pid = 0
    slot_busy_text = normalize_spaces(str((slot_holder or {}).get("busyMessage", "")))
    if normalized_history_filter == "favorites" and current_run_item is not None:
        current_run_key = normalize_spaces(str(current_run_item.get("selectionKey", "")))
        if not find_review_favorite(project_dir, selection_key=current_run_key):
            current_run_item = None
    visible_selection_keys = {
        normalize_spaces(str(item.get("selectionKey", "")))
        for item in history_records
        if normalize_spaces(str(item.get("selectionKey", "")))
    }
    if current_run_item is not None:
        current_selection_key = normalize_spaces(str(current_run_item.get("selectionKey", "")))
        if current_selection_key:
            visible_selection_keys.add(current_selection_key)
    requested_run_id = normalize_spaces(selected_run_id)
    if requested_run_id and requested_run_id not in visible_selection_keys:
        requested_run_id = ""
    if not requested_run_id and current_run_item is not None:
        requested_run_id = normalize_spaces(str(current_run_item.get("selectionKey", "")))
    if not requested_run_id and status not in {"running", "stopping"}:
        requested_run_id = next(
            (
                normalize_spaces(str(item.get("selectionKey", "")))
                for item in history_records
                if normalize_spaces(str(item.get("selectionKey", "")))
            ),
            "",
        )

    detail_run_id = requested_run_id
    run_detail = None
    if requested_run_id == "__active__":
        detail_run_id = normalize_spaces(str((current_run_item or {}).get("runId", "")))
    elif requested_run_id.startswith("path:"):
        favorite_record = find_review_favorite(project_dir, selection_key=requested_run_id)
        review_path = normalize_spaces(str((favorite_record or {}).get("path", ""))) or normalize_spaces(
            str((favorite_record or {}).get("target", ""))
        )
        if review_path:
            run_detail = build_run_detail_snapshot_from_path(project_dir, review_path)
            if run_detail is not None:
                run_detail = {
                    **run_detail,
                    "favorite": True,
                    "favoriteKind": FAVORITE_KIND_PATH,
                    "favoriteSelectionKey": requested_run_id,
                    "reviewPath": review_path,
                }
        detail_run_id = ""

    if run_detail is None and detail_run_id:
        run_detail = build_run_detail_snapshot(project_dir, detail_run_id)
        if run_detail is not None and profile.public:
            matching_item = next(
                (item for item in history_records if normalize_spaces(str(item.get("runId", ""))) == detail_run_id),
                None,
            )
            if matching_item is None and current_run_item is not None:
                current_run_id = normalize_spaces(str(current_run_item.get("runId", "")))
                if current_run_id == detail_run_id:
                    matching_item = current_run_item
            if matching_item is None:
                run_detail = None
    return {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "projectDir": str(project_dir),
        "identity": identity,
        "viewer": {
            "ownerId": effective_viewer.owner_id,
            "displayName": effective_viewer.display_name,
            "email": effective_viewer.email,
            "authenticated": effective_viewer.authenticated,
            "public": effective_viewer.public,
        },
        "status": {
            "status": status,
            "statusLabel": _status_label(status),
            "stage": normalize_spaces(str(visible_status_payload.get("stage", ""))),
            "runId": run_id_from_status,
            "runRoot": normalize_spaces(str(visible_status_payload.get("runRoot", ""))),
            "startedAt": normalize_spaces(str(visible_status_payload.get("startedAt", ""))),
            "finishedAt": normalize_spaces(str(visible_status_payload.get("finishedAt", ""))),
            "error": normalize_spaces(str(visible_status_payload.get("error", ""))),
            "request": _summarize_request_payload(
                visible_status_payload.get("request", {})
                if isinstance(visible_status_payload.get("request"), dict)
                else {}
            ),
            "busy": status in {"running", "stopping"} or active_worker is not None,
            "canStart": status not in {"running", "stopping"} and slot_holder is None and active_worker is None,
            "canStop": status in {"running", "stopping"} and active_worker is not None and viewer_controls_current_task,
            "generationSlotBusy": slot_holder is not None,
            "generationSlot": slot_holder or {},
            "generationSlotText": slot_busy_text,
            "workerAlive": active_worker is not None,
            "workerPid": (
                int(active_worker.get("pid", 0))
                if active_worker and str(active_worker.get("pid", "")).isdigit()
                else status_worker_pid
            ),
        },
        "lastRequest": last_request if isinstance(last_request, dict) else {},
        "currentRunItem": current_run_item,
        "history": history_records,
        "historyStats": {
            **history_stats,
            "running": 1 if current_run_item is not None else 0,
        },
        "historyPage": history_page,
        "selectedRunId": requested_run_id,
        "selectedRunDetail": run_detail,
        "inventory": _build_inventory_payload(project_dir) if profile.allow_inventory else {},
        "config": {
            "sourceKinds": _build_source_kind_config(profile),
            "endStages": [{"id": key, "label": value} for key, value in END_STAGE_LABELS.items()],
            "historyLimit": max(int(history_limit), 1),
            "historyFilters": [
                {"id": "favorites", "label": "收藏"}
                for _ in [0]
                if profile.allow_favorites
            ]
            + [{"id": "active", "label": "有效"}, {"id": "all", "label": "全部"}]
            + ([{"id": "deleted", "label": "已删除"}] if profile.allow_deleted_history else []),
            "permissions": {
                "public": profile.public,
                "allowReviewPath": profile.allow_review_path,
                "allowFavorites": profile.allow_favorites,
                "allowDeleteRun": profile.allow_delete_run,
                "allowInventory": profile.allow_inventory,
                "allowCleanup": profile.allow_cleanup,
                "allowGlobalHistory": profile.allow_global_history,
            },
        },
        "commands": {
            "workbenchStart": "python run_content_workbench.py",
            "productStart": "python run_product.py",
            "generateStart": "python run_generate_product.py --run-label generate_test",
        },
    }
