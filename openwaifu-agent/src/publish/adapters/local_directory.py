from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from io_utils import ensure_dir
from ..local_export import (
    LOCAL_EXPORT_KIND_IMAGE_ONLY,
    TEXT_FILE_SUFFIX,
    default_local_export_name,
    next_available_directory_path,
    next_available_file_path,
    normalize_local_export_options,
)


def publish_to_local_directory(
    *,
    project_dir: Path,
    bundle,
    target_id: str,
    target_config: dict,
    publish_input: dict,
) -> dict:
    published_at = datetime.now().isoformat(timespec="seconds")
    image_path = Path(str(publish_input.get("imagePath", "")).strip()).resolve()
    if not image_path.exists():
        raise RuntimeError(f"发布图片不存在：{image_path}")
    directory_path = Path(str(target_config.get("directoryPath", "")).strip())
    if not directory_path.is_absolute():
        directory_path = (project_dir / directory_path).resolve()
    target_root = ensure_dir(directory_path)
    local_export = normalize_local_export_options(
        target_config.get("localExport", {}),
        default_name=default_local_export_name(publish_input),
    )
    export_name = local_export["name"]
    image_suffix = image_path.suffix.lower() or ".png"
    text_content = str(publish_input.get("socialPostText", "")).strip()

    text_target_path: Path | None = None
    bundle_path: Path | None = None
    if local_export["kind"] == LOCAL_EXPORT_KIND_IMAGE_ONLY:
        image_target_path = next_available_file_path(target_root, base_name=export_name, suffix=image_suffix)
        shutil.copy2(image_path, image_target_path)
    else:
        bundle_path = ensure_dir(next_available_directory_path(target_root, base_name=export_name))
        image_target_path = bundle_path / f"{export_name}{image_suffix}"
        text_target_path = bundle_path / f"{export_name}{TEXT_FILE_SUFFIX}"
        shutil.copy2(image_path, image_target_path)
        text_target_path.write_text(text_content + "\n", encoding="utf-8")
    return {
        "targetId": target_id,
        "adapter": "local_directory",
        "status": "published",
        "publishedAt": published_at,
        "publishId": datetime.now().strftime('%Y%m%dT%H%M%S'),
        "localExport": local_export,
        "exportKind": local_export["kind"],
        "exportName": export_name,
        "containerName": bundle_path.name if bundle_path else "",
        "directoryPath": str(target_root),
        "bundlePath": str(bundle_path) if bundle_path else "",
        "imagePath": str(image_target_path),
        "textPath": str(text_target_path) if text_target_path else "",
        "postUrl": f"file://{(bundle_path or image_target_path).as_posix()}",
    }
