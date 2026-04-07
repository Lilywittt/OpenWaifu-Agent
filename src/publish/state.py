from __future__ import annotations

from pathlib import Path
from typing import Any

from io_utils import ensure_dir, read_json, write_json
from runtime_layout import runtime_root


def publish_state_root(project_dir: Path) -> Path:
    return ensure_dir(runtime_root(project_dir) / "service_state" / "publish")


def published_ledger_path(project_dir: Path) -> Path:
    return publish_state_root(project_dir) / "published_ledger.json"


def append_published_record(project_dir: Path, record: dict[str, Any]) -> None:
    ledger_path = published_ledger_path(project_dir)
    if ledger_path.exists():
        ledger = read_json(ledger_path)
    else:
        ledger = {"records": []}
    records = ledger.get("records")
    if not isinstance(records, list):
        records = []
    records.append(record)
    ledger["records"] = records
    write_json(ledger_path, ledger)
