from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from io_utils import normalize_spaces
from test_pipeline import (
    SOURCE_KIND_CREATIVE_PACKAGE_TEXT,
    SOURCE_KIND_LIVE_SAMPLING,
    SOURCE_KIND_PROMPT_PACKAGE_TEXT,
    SOURCE_KIND_SAMPLE_TEXT,
    SOURCE_KIND_SCENE_DRAFT_TEXT,
)

PROFILE_PRIVATE = "private"
PROFILE_PUBLIC = "public"

PRIVATE_SOURCE_KINDS = ()
PUBLIC_SOURCE_KINDS = (
    SOURCE_KIND_LIVE_SAMPLING,
    SOURCE_KIND_SCENE_DRAFT_TEXT,
    SOURCE_KIND_SAMPLE_TEXT,
    SOURCE_KIND_CREATIVE_PACKAGE_TEXT,
    SOURCE_KIND_PROMPT_PACKAGE_TEXT,
)


@dataclass(frozen=True)
class WorkbenchProfile:
    profile_id: str
    sidecar_id: str
    title: str
    public: bool
    allow_publish: bool
    allow_review_path: bool
    allow_favorites: bool
    allow_delete_run: bool
    allow_inventory: bool
    allow_cleanup: bool
    allow_global_history: bool
    allow_deleted_history: bool
    allowed_source_kinds: tuple[str, ...]

    @property
    def allows_all_source_kinds(self) -> bool:
        return not self.allowed_source_kinds


@dataclass(frozen=True)
class WorkbenchRuntimeSettings:
    profile_id: str
    host: str
    port: int
    refresh_seconds: int
    history_limit: int
    open_browser: bool
    title: str


PRIVATE_PROFILE = WorkbenchProfile(
    profile_id=PROFILE_PRIVATE,
    sidecar_id="content_workbench",
    title="内容测试工作台",
    public=False,
    allow_publish=True,
    allow_review_path=True,
    allow_favorites=True,
    allow_delete_run=True,
    allow_inventory=True,
    allow_cleanup=True,
    allow_global_history=True,
    allow_deleted_history=True,
    allowed_source_kinds=PRIVATE_SOURCE_KINDS,
)

PUBLIC_PROFILE = WorkbenchProfile(
    profile_id=PROFILE_PUBLIC,
    sidecar_id="public_workbench",
    title="内容体验工作台",
    public=True,
    allow_publish=False,
    allow_review_path=False,
    allow_favorites=False,
    allow_delete_run=False,
    allow_inventory=False,
    allow_cleanup=False,
    allow_global_history=False,
    allow_deleted_history=False,
    allowed_source_kinds=PUBLIC_SOURCE_KINDS,
)


def resolve_workbench_profile(profile_id: str) -> WorkbenchProfile:
    normalized = normalize_spaces(profile_id).lower()
    if normalized == PROFILE_PUBLIC:
        return PUBLIC_PROFILE
    return PRIVATE_PROFILE


def workbench_profiles_config_path(project_dir: Path) -> Path:
    return Path(project_dir).resolve() / "config" / "workbench_profiles.json"


def load_workbench_runtime_settings(project_dir: Path, profile: WorkbenchProfile) -> WorkbenchRuntimeSettings:
    path = workbench_profiles_config_path(project_dir)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing workbench profile config: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid workbench profile config: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid workbench profile config: {path}")
    profile_payload = payload.get(profile.profile_id)
    if not isinstance(profile_payload, dict):
        raise RuntimeError(f"Missing {profile.profile_id} profile config in {path}")
    host = normalize_spaces(str(profile_payload.get("host", ""))) or "127.0.0.1"
    try:
        port = int(profile_payload.get("port", 0) or 0)
        refresh_seconds = int(profile_payload.get("refreshSeconds", 0) or 0)
        history_limit = int(profile_payload.get("historyLimit", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid numeric workbench profile config: {path}") from exc
    title = normalize_spaces(str(profile_payload.get("title", ""))) or profile.title
    open_browser = bool(profile_payload.get("openBrowser", False))
    return WorkbenchRuntimeSettings(
        profile_id=profile.profile_id,
        host=host,
        port=port or (8767 if profile.public else 8766),
        refresh_seconds=refresh_seconds or 5,
        history_limit=history_limit or 30,
        open_browser=open_browser,
        title=title,
    )
