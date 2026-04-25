from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from io_utils import ensure_dir, normalize_spaces, write_json
from runtime_layout import runtime_root


def publish_jobs_root(project_dir: Path) -> Path:
    return ensure_dir(runtime_root(project_dir) / "service_state" / "publish" / "jobs")


def publish_job_path(project_dir: Path, job_id: str) -> Path:
    return publish_jobs_root(project_dir) / f"{job_id}.json"


def build_publish_job(*, run_id: str, target_ids: list[str], local_directory: str = "") -> dict[str, Any]:
    created_at = datetime.now().isoformat(timespec="seconds")
    return {
        "jobId": f"{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid4().hex[:8]}",
        "runId": normalize_spaces(run_id),
        "status": "queued",
        "createdAt": created_at,
        "updatedAt": created_at,
        "finishedAt": "",
        "targetIds": list(target_ids),
        "localDirectory": normalize_spaces(local_directory),
        "receipts": [],
        "error": "",
        "artifactsPath": "",
    }


def write_publish_job(project_dir: Path, payload: dict[str, Any]) -> Path:
    path = publish_job_path(project_dir, str(payload.get("jobId", "")).strip())
    write_json(
        path,
        {
            **payload,
            "updatedAt": datetime.now().isoformat(timespec="seconds"),
        },
    )
    return path


def read_publish_job(project_dir: Path, job_id: str) -> dict[str, Any] | None:
    path = publish_job_path(project_dir, normalize_spaces(job_id))
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None
