from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from io_utils import ensure_dir, normalize_spaces, read_json, write_json
from runtime_layout import runtime_root

SURFACE_WORKBENCH_HISTORY = "workbench_history"
SURFACE_WORKBENCH_SOURCE_KINDS = "workbench_source_kinds"
SURFACE_WORKBENCH_END_STAGES = "workbench_end_stages"
SURFACE_OPS_RECENT_RUNS = "ops_recent_runs"

SCOPE_GLOBAL = "global"
SCOPE_PROFILE = "profile"
SCOPE_OWNER = "owner"

_STORE_VERSION = 1


def display_order_store_path(project_dir: Path) -> Path:
    return runtime_root(project_dir) / "service_state" / "shared" / "display_order.json"


def _timestamp_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalize_scope_value(value: str, *, fallback: str) -> str:
    return normalize_spaces(value) or fallback


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _normalize_item_ids(item_ids: list[Any]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in item_ids:
        item_id = normalize_spaces(str(value))
        key = item_id.casefold()
        if not item_id or key in seen:
            continue
        seen.add(key)
        normalized.append(item_id)
    return normalized


def _normalize_entry(raw: dict[str, Any]) -> dict[str, Any] | None:
    surface_id = normalize_spaces(str(raw.get("surfaceId", "")))
    scope_kind = normalize_spaces(str(raw.get("scopeKind", "")))
    scope_id = normalize_spaces(str(raw.get("scopeId", "")))
    item_kind = normalize_spaces(str(raw.get("itemKind", "")))
    item_id = normalize_spaces(str(raw.get("itemId", "")))
    if not all((surface_id, scope_kind, scope_id, item_kind, item_id)):
        return None
    pin_rank = max(_safe_int(raw.get("pinRank")), 0)
    return {
        "surfaceId": surface_id,
        "scopeKind": scope_kind,
        "scopeId": scope_id,
        "itemKind": item_kind,
        "itemId": item_id,
        "pinned": bool(raw.get("pinned", False)),
        "pinRank": pin_rank,
        "hidden": bool(raw.get("hidden", False)),
        "createdAt": normalize_spaces(str(raw.get("createdAt", ""))),
        "updatedAt": normalize_spaces(str(raw.get("updatedAt", ""))),
    }


def _entry_matches(
    entry: dict[str, Any],
    *,
    surface_id: str,
    scope_kind: str,
    scope_id: str,
    item_kind: str | None = None,
    item_id: str | None = None,
) -> bool:
    if normalize_spaces(str(entry.get("surfaceId", ""))) != surface_id:
        return False
    if normalize_spaces(str(entry.get("scopeKind", ""))) != scope_kind:
        return False
    if normalize_spaces(str(entry.get("scopeId", ""))) != scope_id:
        return False
    if item_kind is not None and normalize_spaces(str(entry.get("itemKind", ""))) != item_kind:
        return False
    if item_id is not None and normalize_spaces(str(entry.get("itemId", ""))) != item_id:
        return False
    return True


def _load_store(project_dir: Path) -> dict[str, Any]:
    path = display_order_store_path(project_dir)
    if not path.exists():
        return {"version": _STORE_VERSION, "items": []}
    try:
        payload = read_json(path)
    except Exception:
        return {"version": _STORE_VERSION, "items": []}
    raw_items = payload.get("items", []) if isinstance(payload, dict) else []
    items: list[dict[str, Any]] = []
    for raw_item in raw_items if isinstance(raw_items, list) else []:
        if not isinstance(raw_item, dict):
            continue
        normalized_entry = _normalize_entry(raw_item)
        if normalized_entry is not None:
            items.append(normalized_entry)
    return {"version": _STORE_VERSION, "items": items}


def _sorted_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        entries,
        key=lambda item: (
            normalize_spaces(str(item.get("surfaceId", ""))),
            normalize_spaces(str(item.get("scopeKind", ""))),
            normalize_spaces(str(item.get("scopeId", ""))),
            normalize_spaces(str(item.get("itemKind", ""))),
            0 if bool(item.get("pinned", False)) else 1,
            _safe_int(item.get("pinRank")),
            normalize_spaces(str(item.get("itemId", ""))),
        ),
    )


def _save_store(project_dir: Path, store: dict[str, Any]) -> None:
    path = display_order_store_path(project_dir)
    ensure_dir(path.parent)
    write_json(
        path,
        {
            "version": _STORE_VERSION,
            "items": _sorted_entries(list(store.get("items", []))),
        },
    )


def _surface_entries(
    entries: list[dict[str, Any]],
    *,
    surface_id: str,
    scope_kind: str,
    scope_id: str,
    item_kind: str | None = None,
) -> list[dict[str, Any]]:
    return [
        entry
        for entry in entries
        if _entry_matches(
            entry,
            surface_id=surface_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            item_kind=item_kind,
        )
    ]


def _compact_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for entry in entries:
        if bool(entry.get("pinned", False)) or bool(entry.get("hidden", False)):
            compacted.append(entry)
    return compacted


def _renumber_surface_pins(
    entries: list[dict[str, Any]],
    *,
    surface_id: str,
    scope_kind: str,
    scope_id: str,
    item_kind: str,
) -> None:
    pinned_entries = [
        entry
        for entry in _surface_entries(
            entries,
            surface_id=surface_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            item_kind=item_kind,
        )
        if bool(entry.get("pinned", False))
    ]
    pinned_entries.sort(
        key=lambda entry: (
            _safe_int(entry.get("pinRank")),
            normalize_spaces(str(entry.get("updatedAt", ""))),
            normalize_spaces(str(entry.get("itemId", ""))),
        )
    )
    for index, entry in enumerate(pinned_entries, start=1):
        entry["pinRank"] = index


def list_surface_pin_entries(
    project_dir: Path,
    *,
    surface_id: str,
    scope_kind: str,
    scope_id: str,
    item_kind: str,
) -> list[dict[str, Any]]:
    store = _load_store(Path(project_dir).resolve())
    entries = _surface_entries(
        list(store.get("items", [])),
        surface_id=surface_id,
        scope_kind=scope_kind,
        scope_id=scope_id,
        item_kind=item_kind,
    )
    pinned_entries = [entry for entry in entries if bool(entry.get("pinned", False))]
    pinned_entries.sort(
        key=lambda entry: (
            _safe_int(entry.get("pinRank")),
            normalize_spaces(str(entry.get("updatedAt", ""))),
            normalize_spaces(str(entry.get("itemId", ""))),
        )
    )
    return pinned_entries


def list_surface_pinned_item_ids(
    project_dir: Path,
    *,
    surface_id: str,
    scope_kind: str,
    scope_id: str,
    item_kind: str,
) -> list[str]:
    return [
        normalize_spaces(str(entry.get("itemId", "")))
        for entry in list_surface_pin_entries(
            project_dir,
            surface_id=surface_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            item_kind=item_kind,
        )
        if normalize_spaces(str(entry.get("itemId", "")))
    ]


def pin_surface_items(
    project_dir: Path,
    *,
    surface_id: str,
    scope_kind: str,
    scope_id: str,
    item_kind: str,
    item_ids: list[Any],
    pinned: bool,
) -> dict[str, Any]:
    normalized_ids = _normalize_item_ids(list(item_ids or []))
    if not normalized_ids:
        raise RuntimeError("itemIds 不能为空。")
    project_dir = Path(project_dir).resolve()
    normalized_scope_kind = _normalize_scope_value(scope_kind, fallback=SCOPE_GLOBAL)
    normalized_scope_id = _normalize_scope_value(scope_id, fallback="default")
    normalized_item_kind = _normalize_scope_value(item_kind, fallback="item")
    store = _load_store(project_dir)
    entries = list(store.get("items", []))
    surface_entries = _surface_entries(
        entries,
        surface_id=surface_id,
        scope_kind=normalized_scope_kind,
        scope_id=normalized_scope_id,
        item_kind=normalized_item_kind,
    )
    current_max_rank = max((_safe_int(entry.get("pinRank")) for entry in surface_entries if bool(entry.get("pinned", False))), default=0)
    now = _timestamp_now()
    for item_id in normalized_ids:
        matched_entry = next(
            (
                entry
                for entry in entries
                if _entry_matches(
                    entry,
                    surface_id=surface_id,
                    scope_kind=normalized_scope_kind,
                    scope_id=normalized_scope_id,
                    item_kind=normalized_item_kind,
                    item_id=item_id,
                )
            ),
            None,
        )
        if matched_entry is None:
            matched_entry = {
                "surfaceId": surface_id,
                "scopeKind": normalized_scope_kind,
                "scopeId": normalized_scope_id,
                "itemKind": normalized_item_kind,
                "itemId": item_id,
                "pinned": False,
                "pinRank": 0,
                "hidden": False,
                "createdAt": now,
                "updatedAt": now,
            }
            entries.append(matched_entry)
        if pinned:
            if not bool(matched_entry.get("pinned", False)):
                current_max_rank += 1
                matched_entry["pinRank"] = current_max_rank
            matched_entry["pinned"] = True
        else:
            matched_entry["pinned"] = False
            matched_entry["pinRank"] = 0
        matched_entry["updatedAt"] = now
        if not normalize_spaces(str(matched_entry.get("createdAt", ""))):
            matched_entry["createdAt"] = now
    _renumber_surface_pins(
        entries,
        surface_id=surface_id,
        scope_kind=normalized_scope_kind,
        scope_id=normalized_scope_id,
        item_kind=normalized_item_kind,
    )
    store["items"] = _compact_entries(entries)
    _save_store(project_dir, store)
    return {
        "surfaceId": surface_id,
        "scope": {"kind": normalized_scope_kind, "id": normalized_scope_id},
        "itemKind": normalized_item_kind,
        "pinnedItemIds": list_surface_pinned_item_ids(
            project_dir,
            surface_id=surface_id,
            scope_kind=normalized_scope_kind,
            scope_id=normalized_scope_id,
            item_kind=normalized_item_kind,
        ),
    }


def reorder_surface_pins(
    project_dir: Path,
    *,
    surface_id: str,
    scope_kind: str,
    scope_id: str,
    item_kind: str,
    ordered_item_ids: list[Any],
) -> dict[str, Any]:
    normalized_ids = _normalize_item_ids(list(ordered_item_ids or []))
    if not normalized_ids:
        raise RuntimeError("orderedItemIds 不能为空。")
    project_dir = Path(project_dir).resolve()
    normalized_scope_kind = _normalize_scope_value(scope_kind, fallback=SCOPE_GLOBAL)
    normalized_scope_id = _normalize_scope_value(scope_id, fallback="default")
    normalized_item_kind = _normalize_scope_value(item_kind, fallback="item")
    store = _load_store(project_dir)
    entries = list(store.get("items", []))
    pinned_entries = list_surface_pin_entries(
        project_dir,
        surface_id=surface_id,
        scope_kind=normalized_scope_kind,
        scope_id=normalized_scope_id,
        item_kind=normalized_item_kind,
    )
    current_ids = [normalize_spaces(str(entry.get("itemId", ""))) for entry in pinned_entries]
    if set(normalized_ids) != set(current_ids):
        raise RuntimeError("置顶列表已变化，请刷新后重试。")
    entry_map = {
        normalize_spaces(str(entry.get("itemId", ""))): entry
        for entry in entries
        if _entry_matches(
            entry,
            surface_id=surface_id,
            scope_kind=normalized_scope_kind,
            scope_id=normalized_scope_id,
            item_kind=normalized_item_kind,
        )
    }
    now = _timestamp_now()
    for index, item_id in enumerate(normalized_ids, start=1):
        entry = entry_map.get(item_id)
        if entry is None:
            raise RuntimeError("置顶项不存在，请刷新后重试。")
        entry["pinned"] = True
        entry["pinRank"] = index
        entry["updatedAt"] = now
    store["items"] = _compact_entries(entries)
    _save_store(project_dir, store)
    return {
        "surfaceId": surface_id,
        "scope": {"kind": normalized_scope_kind, "id": normalized_scope_id},
        "itemKind": normalized_item_kind,
        "pinnedItemIds": normalized_ids,
    }


def apply_surface_order(
    project_dir: Path,
    items: list[dict[str, Any]],
    *,
    surface_id: str,
    scope_kind: str,
    scope_id: str,
    item_kind: str,
    item_id_getter: Callable[[dict[str, Any]], Any],
    item_aliases_getter: Callable[[dict[str, Any]], list[Any]] | None = None,
    pin_eligible: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    normalized_scope_kind = _normalize_scope_value(scope_kind, fallback=SCOPE_GLOBAL)
    normalized_scope_id = _normalize_scope_value(scope_id, fallback="default")
    normalized_item_kind = _normalize_scope_value(item_kind, fallback="item")
    pin_entries = list_surface_pin_entries(
        project_dir,
        surface_id=surface_id,
        scope_kind=normalized_scope_kind,
        scope_id=normalized_scope_id,
        item_kind=normalized_item_kind,
    )
    pin_map = {
        normalize_spaces(str(entry.get("itemId", ""))): entry
        for entry in pin_entries
        if normalize_spaces(str(entry.get("itemId", "")))
    }
    eligibility = pin_eligible or (lambda item: True)
    pinned_items_with_rank: list[tuple[int, int, dict[str, Any]]] = []
    regular_items: list[dict[str, Any]] = []
    for base_index, raw_item in enumerate(list(items or [])):
        item = dict(raw_item)
        item_id = normalize_spaces(str(item_id_getter(item)))
        alias_values = item_aliases_getter(item) if item_aliases_getter is not None else []
        item_aliases = _normalize_item_ids(list(alias_values or []))
        is_eligible = bool(item_id) and bool(eligibility(item))
        pin_entry = None
        if item_id:
            pin_entry = pin_map.get(item_id)
        if pin_entry is None:
            for alias_id in item_aliases:
                pin_entry = pin_map.get(alias_id)
                if pin_entry is not None:
                    break
        is_pinned = bool(pin_entry) and is_eligible
        item["surfaceItemId"] = item_id
        item["surfaceItemAliases"] = item_aliases
        item["pinEligible"] = is_eligible
        item["pinned"] = is_pinned
        item["pinRank"] = _safe_int(pin_entry.get("pinRank")) if is_pinned and pin_entry else None
        if is_pinned:
            pinned_items_with_rank.append((_safe_int(pin_entry.get("pinRank")), base_index, item))
        else:
            regular_items.append(item)
    pinned_items_with_rank.sort(key=lambda payload: (payload[0], payload[1], normalize_spaces(str(payload[2].get("surfaceItemId", "")))))
    pinned_items = [item for _, _, item in pinned_items_with_rank]
    return {
        "items": pinned_items + regular_items,
        "pinnedItems": pinned_items,
        "regularItems": regular_items,
        "pinnedItemIds": [normalize_spaces(str(item.get("surfaceItemId", ""))) for item in pinned_items],
        "pinnedCount": len(pinned_items),
        "scope": {"kind": normalized_scope_kind, "id": normalized_scope_id},
        "surfaceId": surface_id,
        "itemKind": normalized_item_kind,
    }
