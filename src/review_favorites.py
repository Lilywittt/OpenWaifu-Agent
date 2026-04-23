from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import ensure_dir, normalize_spaces
from run_detail_store import build_run_detail_snapshot_from_path
from runtime_layout import runtime_root

FAVORITE_KIND_RUN = "run"
FAVORITE_KIND_PATH = "path"
FAVORITE_KINDS = {FAVORITE_KIND_RUN, FAVORITE_KIND_PATH}
_FAVORITES_LOCK_TIMEOUT_SECONDS = 5.0
_FAVORITES_LOCK_STALE_SECONDS = 30.0


def review_favorites_path(project_dir: Path) -> Path:
    return runtime_root(project_dir) / "service_state" / "shared" / "review_favorites.jsonl"


def _review_favorites_lock_path(project_dir: Path) -> Path:
    return review_favorites_path(project_dir).with_suffix(".lock")


def favorite_selection_key(kind: str, target: str) -> str:
    normalized_kind = normalize_spaces(kind).lower()
    normalized_target = normalize_spaces(target)
    if normalized_kind == FAVORITE_KIND_PATH:
        return f"path:{normalized_target}"
    return normalized_target


def _normalize_favorite_kind(value: str) -> str:
    normalized = normalize_spaces(value).lower()
    if normalized not in FAVORITE_KINDS:
        raise RuntimeError("收藏目标类型无效。")
    return normalized


def _normalize_path_target(path_text: str) -> str:
    normalized = normalize_spaces(path_text)
    if not normalized:
        raise RuntimeError("收藏路径不能为空。")
    return str(Path(normalized).expanduser().resolve())


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
                continue
            if isinstance(payload, dict):
                records.append(payload)
    return records


def _write_jsonl_records(path: Path, records: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


class _ReviewFavoritesLock:
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir).resolve()
        self.path = _review_favorites_lock_path(self.project_dir)
        self._fd: int | None = None

    def __enter__(self) -> "_ReviewFavoritesLock":
        ensure_dir(self.path.parent)
        deadline = time.monotonic() + _FAVORITES_LOCK_TIMEOUT_SECONDS
        while True:
            try:
                self._fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self._fd, str(os.getpid()).encode("ascii", errors="ignore"))
                return self
            except FileExistsError:
                try:
                    stat_result = self.path.stat()
                except OSError:
                    continue
                age_seconds = time.time() - stat_result.st_mtime
                if age_seconds >= _FAVORITES_LOCK_STALE_SECONDS:
                    try:
                        self.path.unlink()
                    except OSError:
                        pass
                    continue
                if time.monotonic() >= deadline:
                    raise RuntimeError("收藏索引正被其他进程占用，请稍后再试。")
                time.sleep(0.05)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        try:
            self.path.unlink()
        except OSError:
            pass


def list_review_favorites(project_dir: Path) -> list[dict[str, Any]]:
    records = [dict(record) for record in _read_jsonl_records(review_favorites_path(project_dir))]
    records.sort(
        key=lambda item: (
            normalize_spaces(str(item.get("savedAt", ""))),
            normalize_spaces(str(item.get("selectionKey", ""))),
        ),
        reverse=True,
    )
    return records


def find_review_favorite(
    project_dir: Path,
    *,
    selection_key: str = "",
    kind: str = "",
    target: str = "",
) -> dict[str, Any] | None:
    normalized_selection_key = normalize_spaces(selection_key)
    normalized_kind = normalize_spaces(kind).lower()
    normalized_target = normalize_spaces(target)
    for record in list_review_favorites(project_dir):
        if normalized_selection_key and normalize_spaces(str(record.get("selectionKey", ""))) == normalized_selection_key:
            return record
        if (
            normalized_kind
            and normalized_target
            and normalize_spaces(str(record.get("kind", ""))).lower() == normalized_kind
            and normalize_spaces(str(record.get("target", ""))) == normalized_target
        ):
            return record
    return None


def favorite_run_ids(project_dir: Path) -> set[str]:
    run_ids: set[str] = set()
    for record in list_review_favorites(project_dir):
        run_id = normalize_spaces(str(record.get("runId", "")))
        if run_id:
            run_ids.add(run_id)
    return run_ids


def is_run_favorited(project_dir: Path, run_id: str) -> bool:
    return normalize_spaces(run_id) in favorite_run_ids(project_dir)


def _build_favorite_record(project_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    kind = _normalize_favorite_kind(str(payload.get("kind", "")))
    run_id = normalize_spaces(str(payload.get("runId", "")))
    run_root = normalize_spaces(str(payload.get("runRoot", "")))
    label = normalize_spaces(str(payload.get("label", "")))
    source_kind = normalize_spaces(str(payload.get("sourceKind", "")))
    end_stage = normalize_spaces(str(payload.get("endStage", "")))
    scene_draft_premise = normalize_spaces(str(payload.get("sceneDraftPremiseZh", "")))

    if kind == FAVORITE_KIND_RUN:
        target = normalize_spaces(str(payload.get("runId", "")))
        if not target:
            raise RuntimeError("收藏 run 时必须提供 runId。")
        title = scene_draft_premise or label or target
        return {
            "kind": kind,
            "target": target,
            "selectionKey": favorite_selection_key(kind, target),
            "savedAt": datetime.now().isoformat(timespec="seconds"),
            "title": title,
            "label": label,
            "sourceKind": source_kind,
            "endStage": end_stage,
            "sceneDraftPremiseZh": scene_draft_premise,
            "runId": target,
            "runRoot": run_root,
            "path": "",
        }

    path_target = _normalize_path_target(str(payload.get("path", "")))
    detail = build_run_detail_snapshot_from_path(project_dir, path_target)
    detail_run_id = normalize_spaces(str((detail or {}).get("runId", "")))
    detail_run_root = normalize_spaces(str((detail or {}).get("runRoot", "")))
    detail_title = normalize_spaces(str((detail or {}).get("detailTitle", "")))
    return {
        "kind": kind,
        "target": path_target,
        "selectionKey": favorite_selection_key(kind, path_target),
        "savedAt": datetime.now().isoformat(timespec="seconds"),
        "title": scene_draft_premise or label or detail_title or Path(path_target).name or path_target,
        "label": label,
        "sourceKind": source_kind,
        "endStage": end_stage,
        "sceneDraftPremiseZh": scene_draft_premise,
        "runId": run_id or detail_run_id,
        "runRoot": run_root or detail_run_root,
        "path": path_target,
    }


def toggle_review_favorite(project_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    resolved_project_dir = Path(project_dir).resolve()
    with _ReviewFavoritesLock(resolved_project_dir):
        record = _build_favorite_record(resolved_project_dir, payload)
        path = review_favorites_path(resolved_project_dir)
        records = list_review_favorites(resolved_project_dir)
        selection_key = normalize_spaces(str(record.get("selectionKey", "")))
        existing = next(
            (item for item in records if normalize_spaces(str(item.get("selectionKey", ""))) == selection_key),
            None,
        )
        if existing is not None:
            remaining = [
                item
                for item in records
                if normalize_spaces(str(item.get("selectionKey", ""))) != selection_key
            ]
            _write_jsonl_records(path, remaining)
            return {
                "favorited": False,
                "selectionKey": selection_key,
                "kind": normalize_spaces(str(existing.get("kind", ""))),
                "target": normalize_spaces(str(existing.get("target", ""))),
                "entry": existing,
            }

        records.append(record)
        records.sort(
            key=lambda item: (
                normalize_spaces(str(item.get("savedAt", ""))),
                normalize_spaces(str(item.get("selectionKey", ""))),
            ),
            reverse=True,
        )
        _write_jsonl_records(path, records)
        return {
            "favorited": True,
            "selectionKey": selection_key,
            "kind": normalize_spaces(str(record.get("kind", ""))),
            "target": normalize_spaces(str(record.get("target", ""))),
            "entry": record,
        }
