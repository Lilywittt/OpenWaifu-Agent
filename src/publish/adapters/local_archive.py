from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import ensure_dir, write_json
from runtime_layout import sanitize_segment


def _resolve_archive_root(project_dir: Path, archive_root: str) -> Path:
    raw_path = Path(str(archive_root or "").strip())
    if raw_path.is_absolute():
        return ensure_dir(raw_path)
    return ensure_dir((project_dir / raw_path).resolve())


def publish_to_local_archive(
    *,
    project_dir: Path,
    bundle,
    target_id: str,
    target_config: dict[str, Any],
    publish_input: dict[str, Any],
) -> dict[str, Any]:
    published_at = datetime.now().isoformat(timespec="seconds")
    publish_id = f"{datetime.now().strftime('%Y%m%dT%H%M%S')}_{sanitize_segment(bundle.run_id)}"
    archive_root = _resolve_archive_root(project_dir, str(target_config.get("archiveRoot", "runtime/service_state/publish/local_archive")))
    target_root = ensure_dir(archive_root / sanitize_segment(target_id))
    archive_record_path = target_root / f"{publish_id}.json"

    archive_record = {
        "meta": {
            "publishedAt": published_at,
            "publishId": publish_id,
        },
        "targetId": target_id,
        "targetConfig": target_config,
        "publishInput": publish_input,
    }
    write_json(archive_record_path, archive_record)

    return {
        "targetId": target_id,
        "adapter": "local_archive",
        "status": "published",
        "publishedAt": published_at,
        "publishId": publish_id,
        "postUrl": f"local-archive://{target_id}/{publish_id}",
        "archiveRecordPath": str(archive_record_path),
    }
