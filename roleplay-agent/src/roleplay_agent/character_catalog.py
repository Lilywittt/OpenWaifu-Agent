from __future__ import annotations

import copy
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .io_utils import ensure_dir, read_json, write_json


CATALOG_PATH = Path("config") / "characters.json"
DEFAULT_CHARACTER_ID = "default"
SCHEMA_VERSION = 1


def normalize_character_id(raw: str, *, fallback: str = DEFAULT_CHARACTER_ID) -> str:
    text = str(raw or "").strip().lower()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_\-\u4e00-\u9fa5]", "_", text)
    text = re.sub(r"_+", "_", text).strip("_-")
    return text or fallback


def character_path(project_dir: Path, character_id: str) -> Path:
    safe_id = normalize_character_id(character_id)
    return project_dir / "characters" / f"{safe_id}.json"


def trash_path(project_dir: Path, character_id: str) -> Path:
    safe_id = normalize_character_id(character_id)
    return project_dir / "runtime" / "character_trash" / f"{safe_id}.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _character_display_name(payload: dict[str, Any], character_id: str) -> str:
    for key in ("name", "displayName", "title"):
        value = str(payload.get(key, "") or "").strip()
        if value:
            return value
    return "默认角色" if character_id == DEFAULT_CHARACTER_ID else character_id


def _sections_from_legacy(payload: dict[str, Any]) -> list[dict[str, str]]:
    if isinstance(payload.get("sections"), list):
        return [
            {
                "id": str(item.get("id", "") or f"section_{index + 1}"),
                "title": str(item.get("title", item.get("label", "")) or ""),
                "content": str(item.get("content", "") or ""),
            }
            for index, item in enumerate(payload["sections"])
            if isinstance(item, dict)
        ]
    if isinstance(payload.get("fields"), list):
        return [
            {
                "id": str(item.get("id", "") or f"section_{index + 1}"),
                "title": str(item.get("label", item.get("title", "")) or ""),
                "content": str(item.get("content", "") or ""),
            }
            for index, item in enumerate(payload["fields"])
            if isinstance(item, dict)
        ]
    sections: list[dict[str, str]] = []
    for source_key in ("subjectProfile", "roleplaySource", "editableRoleplay"):
        source = payload.get(source_key)
        if not isinstance(source, dict):
            continue
        for key, value in source.items():
            if key in {"id", "sourceProject", "sourceProfilePath", "displayName", "name"}:
                continue
            text = value if isinstance(value, str) else ""
            if text:
                sections.append({"id": str(key), "title": str(key), "content": text})
    return sections


def normalize_character_payload(payload: dict[str, Any], character_id: str, *, name: str = "") -> dict[str, Any]:
    safe_id = normalize_character_id(character_id)
    clean_name = str(name or "").strip() or _character_display_name(payload, safe_id)
    metadata = copy.deepcopy(payload.get("metadata")) if isinstance(payload.get("metadata"), dict) else {}
    source: dict[str, Any] = {}
    if payload.get("sourceProject"):
        source["project"] = payload.get("sourceProject")
    if payload.get("sourceProfilePath"):
        source["profilePath"] = payload.get("sourceProfilePath")
    if source:
        metadata["source"] = source
    metadata.setdefault("updatedAt", _now())
    return {
        "schemaVersion": SCHEMA_VERSION,
        "id": safe_id,
        "name": clean_name,
        "sections": _sections_from_legacy(payload),
        "metadata": metadata,
    }


def read_character(project_dir: Path, character_id: str) -> dict[str, Any]:
    safe_id = normalize_character_id(character_id)
    payload = read_json(character_path(project_dir, safe_id), default={})
    if not isinstance(payload, dict):
        payload = {}
    normalized = normalize_character_payload(payload, safe_id)
    if payload != normalized:
        write_json(character_path(project_dir, safe_id), normalized)
    return normalized


def write_character(project_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    safe_id = normalize_character_id(str(payload.get("id", DEFAULT_CHARACTER_ID)))
    previous = read_json(character_path(project_dir, safe_id), default={})
    if not isinstance(previous, dict):
        previous = {}
    merged = {**previous, **payload}
    metadata = copy.deepcopy(merged.get("metadata")) if isinstance(merged.get("metadata"), dict) else {}
    metadata["updatedAt"] = _now()
    merged["metadata"] = metadata
    normalized = normalize_character_payload(merged, safe_id, name=str(merged.get("name", "") or ""))
    write_json(character_path(project_dir, safe_id), normalized)
    return normalized


def _is_deleted_character(project_dir: Path, character_id: str) -> bool:
    payload = read_character(project_dir, character_id)
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    return bool(str(metadata.get("deletedAt", "") or "").strip())


def _move_legacy_deleted_character(project_dir: Path, path: Path) -> dict[str, Any] | None:
    payload = read_json(path, default={})
    if not isinstance(payload, dict):
        return None
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    if not str(metadata.get("deletedAt", "") or "").strip():
        return None
    character_id = normalize_character_id(str(payload.get("id", path.stem)))
    ensure_dir(trash_path(project_dir, character_id).parent)
    write_json(trash_path(project_dir, character_id), normalize_character_payload(payload, character_id))
    path.unlink()
    return read_json(trash_path(project_dir, character_id), default={})


def trashed_characters(project_dir: Path) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    character_root = project_dir / "characters"
    if character_root.exists():
        for path in sorted(character_root.glob("*.json")):
            _move_legacy_deleted_character(project_dir, path)
    root = project_dir / "runtime" / "character_trash"
    if not root.exists():
        return result
    for path in sorted(root.glob("*.json")):
        payload = read_json(path, default={})
        if not isinstance(payload, dict):
            continue
        character_id = normalize_character_id(str(payload.get("id", path.stem)))
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        deleted_at = str(metadata.get("deletedAt", "") or "").strip()
        if deleted_at:
            result.append({"id": character_id, "name": str(payload.get("name", character_id)), "deletedAt": deleted_at})
    return result


def _default_catalog(project_dir: Path) -> dict[str, Any]:
    payload = read_character(project_dir, DEFAULT_CHARACTER_ID)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "activeCharacterId": DEFAULT_CHARACTER_ID,
        "order": [DEFAULT_CHARACTER_ID],
        "items": [{"id": DEFAULT_CHARACTER_ID, "name": _character_display_name(payload, DEFAULT_CHARACTER_ID)}],
    }


def load_character_catalog(project_dir: Path) -> dict[str, Any]:
    character_root = project_dir / "characters"
    if character_root.exists():
        for character_file in sorted(character_root.glob("*.json")):
            _move_legacy_deleted_character(project_dir, character_file)
    path = project_dir / CATALOG_PATH
    payload = read_json(path) if path.exists() else None
    if not isinstance(payload, dict):
        payload = _default_catalog(project_dir)
        write_character_catalog(project_dir, payload)
    order = payload.get("order")
    if not isinstance(order, list) or not order:
        items = payload.get("items")
        if isinstance(items, list):
            order = [normalize_character_id(str(item.get("id", ""))) for item in items if isinstance(item, dict)]
        else:
            order = []
    order = [character_id for character_id in [normalize_character_id(str(item)) for item in order] if character_id]
    order = [character_id for character_id in order if not _is_deleted_character(project_dir, character_id)]
    if not order:
        payload = _default_catalog(project_dir)
        write_character_catalog(project_dir, payload)
        order = payload["order"]
    active_id = normalize_character_id(str(payload.get("activeCharacterId", order[0])))
    if active_id not in set(order):
        active_id = order[0]
        payload["activeCharacterId"] = active_id
        write_character_catalog(project_dir, payload)
    items = [{"id": character_id, "name": read_character(project_dir, character_id).get("name", character_id)} for character_id in order]
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "activeCharacterId": active_id,
        "order": order,
        "items": items,
    }
    write_character_catalog(project_dir, payload)
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "activeCharacterId": active_id,
        "order": order,
        "items": items,
    }
    return payload


def write_character_catalog(project_dir: Path, payload: dict[str, Any]) -> None:
    ensure_dir((project_dir / CATALOG_PATH).parent)
    order = payload.get("order")
    if not isinstance(order, list):
        order = [item.get("id") for item in payload.get("items", []) if isinstance(item, dict)]
    order = [normalize_character_id(str(item)) for item in order if str(item or "").strip()]
    active_id = normalize_character_id(str(payload.get("activeCharacterId", order[0] if order else DEFAULT_CHARACTER_ID)))
    write_json(
        project_dir / CATALOG_PATH,
        {
            "schemaVersion": SCHEMA_VERSION,
            "activeCharacterId": active_id,
            "order": order or [DEFAULT_CHARACTER_ID],
        },
    )


def active_character_id(project_dir: Path) -> str:
    return normalize_character_id(str(load_character_catalog(project_dir).get("activeCharacterId", DEFAULT_CHARACTER_ID)))


def set_active_character(project_dir: Path, character_id: str) -> dict[str, Any]:
    catalog = load_character_catalog(project_dir)
    safe_id = normalize_character_id(character_id)
    if safe_id not in set(catalog["order"]):
        raise RuntimeError("character does not exist.")
    catalog["activeCharacterId"] = safe_id
    write_character_catalog(project_dir, catalog)
    return load_character_catalog(project_dir)


def create_character(project_dir: Path, *, name: str = "", source_id: str | None = None) -> dict[str, Any]:
    catalog = load_character_catalog(project_dir)
    base_name = str(name or "").strip() or "新角色"
    existing = {normalize_character_id(str(item.get("id", ""))) for item in catalog["items"] if isinstance(item, dict)}
    existing_names = {str(item.get("name", "") or "").strip() for item in catalog["items"] if isinstance(item, dict)}
    existing_names.update(str(item.get("name", "") or "").strip() for item in trashed_characters(project_dir))
    clean_name = base_name
    base_id = normalize_character_id(clean_name, fallback="character")
    safe_id = base_id
    index = 2
    while (
        clean_name in existing_names
        or safe_id in existing
        or character_path(project_dir, safe_id).exists()
        or trash_path(project_dir, safe_id).exists()
    ):
        clean_name = f"{base_name} {index}"
        safe_id = normalize_character_id(clean_name, fallback=f"character_{index}")
        index += 1
    if source_id:
        source_payload = read_character(project_dir, source_id)
        payload = copy.deepcopy(source_payload) if isinstance(source_payload, dict) else {}
    else:
        payload = {"id": safe_id, "name": clean_name, "sections": []}
    payload["id"] = safe_id
    payload["name"] = clean_name
    write_character(project_dir, payload)
    catalog["order"].append(safe_id)
    catalog["activeCharacterId"] = safe_id
    write_character_catalog(project_dir, catalog)
    return load_character_catalog(project_dir)


def update_character_name(project_dir: Path, *, character_id: str, name: str) -> dict[str, Any]:
    catalog = load_character_catalog(project_dir)
    safe_id = normalize_character_id(character_id)
    clean_name = str(name or "").strip() or safe_id
    payload = read_character(project_dir, safe_id)
    payload["name"] = clean_name
    write_character(project_dir, payload)
    return load_character_catalog(project_dir)


def delete_character(project_dir: Path, character_id: str) -> dict[str, Any]:
    catalog = load_character_catalog(project_dir)
    safe_id = normalize_character_id(character_id)
    order = [item for item in catalog["order"] if normalize_character_id(str(item)) != safe_id]
    if not order:
        raise RuntimeError("at least one character is required.")
    catalog["order"] = order
    if normalize_character_id(str(catalog.get("activeCharacterId", ""))) == safe_id:
        catalog["activeCharacterId"] = normalize_character_id(str(order[0]))
    path = character_path(project_dir, safe_id)
    if path.exists():
        payload = read_character(project_dir, safe_id)
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        metadata["deletedAt"] = _now()
        payload["metadata"] = metadata
        ensure_dir(trash_path(project_dir, safe_id).parent)
        write_json(trash_path(project_dir, safe_id), payload)
        path.unlink()
    write_character_catalog(project_dir, catalog)
    return load_character_catalog(project_dir)


def restore_character(project_dir: Path, character_id: str) -> dict[str, Any]:
    catalog = load_character_catalog(project_dir)
    safe_id = normalize_character_id(character_id)
    trash = trash_path(project_dir, safe_id)
    raw_payload = read_json(trash, default={}) if trash.exists() else read_json(character_path(project_dir, safe_id), default={})
    if not isinstance(raw_payload, dict):
        raise RuntimeError("character is not in trash.")
    payload = normalize_character_payload(raw_payload, safe_id)
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    metadata.pop("deletedAt", None)
    payload["metadata"] = metadata
    write_character(project_dir, payload)
    if trash.exists():
        trash.unlink()
    if safe_id not in catalog["order"]:
        catalog["order"].append(safe_id)
    catalog["activeCharacterId"] = safe_id
    write_character_catalog(project_dir, catalog)
    return load_character_catalog(project_dir)


def purge_character(project_dir: Path, character_id: str) -> dict[str, Any]:
    catalog = load_character_catalog(project_dir)
    safe_id = normalize_character_id(character_id)
    if safe_id in catalog["order"]:
        raise RuntimeError("character must be deleted before purge.")
    for path in (trash_path(project_dir, safe_id), character_path(project_dir, safe_id)):
        if path.exists():
            path.unlink()
    write_character_catalog(project_dir, catalog)
    return load_character_catalog(project_dir)
