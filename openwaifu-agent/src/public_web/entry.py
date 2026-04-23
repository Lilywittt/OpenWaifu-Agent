from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from workbench.profile import PUBLIC_PROFILE
from workbench.service import (
    fetch_existing_workbench_health,
    run_workbench_server,
    workbench_browser_url,
)


def _public_worker_command(project_dir: Path, request_id: str) -> list[str]:
    return [
        str(Path(sys.executable).resolve()),
        str(Path(project_dir).resolve() / "run_public_workbench.py"),
        "worker",
        "--request-id",
        request_id,
    ]


def public_workbench_browser_url(host: str, port: int) -> str:
    return workbench_browser_url(host, port)


def fetch_existing_public_workbench_health(url: str, *, timeout_seconds: int = 2) -> dict[str, Any] | None:
    return fetch_existing_workbench_health(
        url,
        expected_service=PUBLIC_PROFILE.sidecar_id,
        timeout_seconds=timeout_seconds,
    )


def run_public_workbench_server(
    project_dir: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8767,
    refresh_seconds: int = 5,
    history_limit: int = 30,
    open_browser: bool = False,
) -> None:
    return run_workbench_server(
        project_dir,
        profile=PUBLIC_PROFILE,
        worker_command_builder=lambda request_id: _public_worker_command(project_dir, request_id),
        host=host,
        port=port,
        refresh_seconds=refresh_seconds,
        history_limit=history_limit,
        open_browser=open_browser,
    )
