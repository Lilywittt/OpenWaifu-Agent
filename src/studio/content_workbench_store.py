from __future__ import annotations

from pathlib import Path
from typing import Any

from process_utils import is_process_alive
from workbench import store as _store

DEFAULT_CLEANUP_OLDER_THAN_DAYS = _store.DEFAULT_CLEANUP_OLDER_THAN_DAYS
DEFAULT_HISTORY_LIMIT = _store.DEFAULT_HISTORY_LIMIT
append_history_record = _store.append_history_record
append_run_index_record = _store.append_run_index_record
can_access_workbench_run = _store.can_access_workbench_run
clear_active_request = _store.clear_active_request
clear_active_worker = _store.clear_active_worker
clear_workbench_stop_request = _store.clear_workbench_stop_request
content_workbench_state_root = _store.content_workbench_state_root
delete_workbench_run = _store.delete_workbench_run
finalize_workbench_runtime = _store.finalize_workbench_runtime
generate_cleanup_report = _store.generate_cleanup_report
is_workbench_stop_requested = _store.is_workbench_stop_requested
legacy_content_workbench_state_roots = _store.legacy_content_workbench_state_roots
migrate_legacy_content_workbench_state = _store.migrate_legacy_content_workbench_state
normalize_stale_workbench_status = _store.normalize_stale_workbench_status
read_active_request = _store.read_active_request
read_last_request = _store.read_last_request
read_workbench_status = _store.read_workbench_status
request_workbench_stop = _store.request_workbench_stop
toggle_workbench_favorite = _store.toggle_workbench_favorite
workbench_inventory_paths = _store.workbench_inventory_paths
write_active_request = _store.write_active_request
write_active_worker = _store.write_active_worker
write_last_request = _store.write_last_request
write_workbench_status = _store.write_workbench_status


def _with_local_process_probe(func, *args: Any, **kwargs: Any):
    original = _store.is_process_alive
    _store.is_process_alive = is_process_alive
    try:
        return func(*args, **kwargs)
    finally:
        _store.is_process_alive = original


def read_active_worker(project_dir: Path, *, cleanup_stale: bool = True) -> dict[str, Any] | None:
    return _with_local_process_probe(_store.read_active_worker, project_dir, cleanup_stale=cleanup_stale)


def reconcile_workbench_runtime_state(project_dir: Path) -> bool:
    return _with_local_process_probe(_store.reconcile_workbench_runtime_state, project_dir)


def build_content_workbench_snapshot(
    project_dir: Path,
    *,
    selected_run_id: str = "",
    history_filter: str = "active",
    history_limit: int = DEFAULT_HISTORY_LIMIT,
    viewer=None,
    profile=_store.PRIVATE_PROFILE,
) -> dict[str, Any]:
    return _with_local_process_probe(
        _store.build_content_workbench_snapshot,
        project_dir,
        selected_run_id=selected_run_id,
        history_filter=history_filter,
        history_limit=history_limit,
        viewer=viewer,
        profile=profile,
    )


__all__ = [
    "DEFAULT_CLEANUP_OLDER_THAN_DAYS",
    "DEFAULT_HISTORY_LIMIT",
    "append_history_record",
    "append_run_index_record",
    "build_content_workbench_snapshot",
    "can_access_workbench_run",
    "clear_active_request",
    "clear_active_worker",
    "clear_workbench_stop_request",
    "content_workbench_state_root",
    "delete_workbench_run",
    "finalize_workbench_runtime",
    "generate_cleanup_report",
    "is_process_alive",
    "is_workbench_stop_requested",
    "legacy_content_workbench_state_roots",
    "migrate_legacy_content_workbench_state",
    "normalize_stale_workbench_status",
    "read_active_request",
    "read_active_worker",
    "read_last_request",
    "read_workbench_status",
    "reconcile_workbench_runtime_state",
    "request_workbench_stop",
    "toggle_workbench_favorite",
    "workbench_inventory_paths",
    "write_active_request",
    "write_active_worker",
    "write_last_request",
    "write_workbench_status",
]
