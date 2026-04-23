from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from workbench.identity import resolve_workbench_viewer
from workbench.profile import PRIVATE_PROFILE
from workbench.service import (
    WorkbenchManager,
    _make_handler as _shared_make_handler,
    fetch_existing_workbench_health,
    probe_existing_workbench,
    run_workbench_server,
    workbench_browser_url,
)


def _private_worker_command(project_dir: Path, request_id: str) -> list[str]:
    return [
        str(Path(sys.executable).resolve()),
        str(Path(project_dir).resolve() / "run_content_workbench.py"),
        "worker",
        "--request-id",
        request_id,
    ]


def content_workbench_browser_url(host: str, port: int) -> str:
    return workbench_browser_url(host, port)


def fetch_existing_content_workbench_health(url: str, *, timeout_seconds: int = 2) -> dict[str, Any] | None:
    return fetch_existing_workbench_health(
        url,
        expected_service=PRIVATE_PROFILE.sidecar_id,
        timeout_seconds=timeout_seconds,
    )


def probe_existing_content_workbench(url: str, *, timeout_seconds: int = 2) -> bool:
    return probe_existing_workbench(
        url,
        expected_service=PRIVATE_PROFILE.sidecar_id,
        timeout_seconds=timeout_seconds,
    )


class ContentWorkbenchManager(WorkbenchManager):
    def __init__(self, project_dir: Path):
        super().__init__(
            project_dir,
            profile=PRIVATE_PROFILE,
            worker_command_builder=lambda request_id: _private_worker_command(project_dir, request_id),
        )

    def start_task(self, payload: dict[str, Any], *, viewer=None) -> dict[str, Any]:
        return super().start_task(payload, viewer=viewer or resolve_workbench_viewer(PRIVATE_PROFILE))

    def stop_task(self, *, viewer=None) -> dict[str, Any]:
        return super().stop_task(viewer=viewer or resolve_workbench_viewer(PRIVATE_PROFILE))

    def rerun_last(self, *, viewer=None) -> dict[str, Any]:
        return super().rerun_last(viewer=viewer or resolve_workbench_viewer(PRIVATE_PROFILE))


class _PrivateManagerAdapter:
    def __init__(self, manager: Any):
        self._manager = manager

    def is_busy(self) -> bool:
        return bool(self._manager.is_busy())

    def start_task(self, payload: dict[str, Any], *, viewer) -> dict[str, Any]:
        try:
            return self._manager.start_task(payload, viewer=viewer)
        except TypeError:
            return self._manager.start_task(payload)

    def stop_task(self, *, viewer) -> dict[str, Any]:
        try:
            return self._manager.stop_task(viewer=viewer)
        except TypeError:
            return self._manager.stop_task()

    def rerun_last(self, *, viewer) -> dict[str, Any]:
        try:
            return self._manager.rerun_last(viewer=viewer)
        except TypeError:
            return self._manager.rerun_last()

    def shutdown(self) -> None:
        shutdown = getattr(self._manager, "shutdown", None)
        if callable(shutdown):
            shutdown()


def _make_handler(
    *,
    project_dir: Path,
    refresh_seconds: int,
    history_limit: int,
    manager: Any,
):
    return _shared_make_handler(
        project_dir=project_dir,
        refresh_seconds=refresh_seconds,
        history_limit=history_limit,
        manager=_PrivateManagerAdapter(manager),
        profile=PRIVATE_PROFILE,
    )


def run_content_workbench_server(
    project_dir: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8766,
    refresh_seconds: int = 5,
    history_limit: int = 30,
    open_browser: bool = False,
) -> None:
    return run_workbench_server(
        project_dir,
        profile=PRIVATE_PROFILE,
        worker_command_builder=lambda request_id: _private_worker_command(project_dir, request_id),
        host=host,
        port=port,
        refresh_seconds=refresh_seconds,
        history_limit=history_limit,
        open_browser=open_browser,
    )


__all__ = [
    "ContentWorkbenchManager",
    "_make_handler",
    "content_workbench_browser_url",
    "fetch_existing_content_workbench_health",
    "probe_existing_content_workbench",
    "run_content_workbench_server",
]
