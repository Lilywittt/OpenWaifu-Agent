from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any

from .config import resolve_character_path
from .events import active_events_text
from .io_utils import read_json, read_text
from .lorebook import activated_lore_text
from .persona import load_user_persona
from .paths import resolve_project_path


@dataclass(frozen=True)
class PromptBundle:
    system_prompt: str
    character: dict[str, Any]
    source_paths: dict[str, str]


def load_character(project_dir: Path, character_id: str | None = None) -> dict[str, Any]:
    path = resolve_character_path(project_dir, character_id)
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise RuntimeError(f"character card must be a JSON object: {path}")
    return payload


def _load_prompt_manifest(project_dir: Path) -> dict[str, Any]:
    payload = read_json(project_dir / "config" / "prompt_manifest.json")
    if not isinstance(payload, dict):
        raise RuntimeError("config/prompt_manifest.json must be a JSON object.")
    return payload


def _load_fragments(project_dir: Path, manifest: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    fragments: dict[str, str] = {}
    source_paths: dict[str, str] = {}
    raw_fragments = manifest.get("fragments", {})
    if not isinstance(raw_fragments, dict):
        raise RuntimeError("prompt_manifest.fragments must be a JSON object.")
    for key, raw_path in raw_fragments.items():
        path = resolve_project_path(project_dir, str(raw_path))
        fragments[str(key)] = read_text(path)
        source_paths[str(key)] = str(path)
    return fragments, source_paths


def _character_context_for_model(character: dict[str, Any]) -> dict[str, Any]:
    if isinstance(character.get("sections"), list):
        return {
            "name": str(character.get("name", character.get("displayName", "")) or "").strip(),
            "sections": [
                {
                    "title": str(section.get("title", section.get("label", "")) or "").strip(),
                    "content": str(section.get("content", "") or "").strip(),
                }
                for section in character["sections"]
                if isinstance(section, dict) and str(section.get("content", "") or "").strip()
            ],
        }
    payload = {
        key: value
        for key, value in character.items()
        if key not in {"schemaVersion", "metadata", "sourceProject", "sourceProfilePath"}
    }
    editable = payload.get("editableRoleplay")
    if isinstance(editable, dict):
        payload["editableRoleplay"] = {
            key: value
            for key, value in editable.items()
            if value not in ("", None, [], {})
        }
        if not payload["editableRoleplay"]:
            payload.pop("editableRoleplay", None)
    return payload


def _json_section(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ""
    meaningful = {key: value for key, value in payload.items() if value not in ("", None, [], {})}
    if not meaningful:
        return ""
    return json.dumps(meaningful, ensure_ascii=False, indent=2)


def build_system_prompt(
    project_dir: Path,
    *,
    user_id: str = "",
    character_id: str | None = None,
    memory_summary: str = "",
    context_text: str = "",
    persona_id: str = "default",
) -> PromptBundle:
    manifest = _load_prompt_manifest(project_dir)
    template_path = resolve_project_path(project_dir, str(manifest.get("systemTemplate", "prompts/system.md")))
    template_text = read_text(template_path)
    fragments, source_paths = _load_fragments(project_dir, manifest)
    character_path = resolve_character_path(project_dir, character_id)
    character = load_character(project_dir, character_id)
    persona = load_user_persona(project_dir, persona_id)
    active_events = active_events_text(project_dir)
    active_lore = activated_lore_text(project_dir, context_text)
    values = {
        **fragments,
        "character_card_json": json.dumps(_character_context_for_model(character), ensure_ascii=False, indent=2),
        "user_persona_json": _json_section(persona),
        "active_events": active_events,
        "active_lore": active_lore,
        "memory_summary": str(memory_summary or "").strip(),
        "user_id": str(user_id or "").strip(),
    }
    rendered = "\n".join(
        line.rstrip()
        for line in Template(template_text).safe_substitute(values).splitlines()
        if line.strip()
    ).strip()
    if not rendered:
        raise RuntimeError("system prompt is empty.")
    source_paths["systemTemplate"] = str(template_path)
    source_paths["character"] = str(character_path)
    source_paths["persona"] = str(resolve_project_path(project_dir, Path("personas") / f"{persona_id}.json"))
    source_paths["events"] = str(project_dir / "events" / "active_events.json")
    source_paths["lorebook"] = str(project_dir / "lorebooks" / "default.json")
    return PromptBundle(system_prompt=rendered, character=character, source_paths=source_paths)


def load_post_history_instructions(project_dir: Path) -> str:
    manifest = _load_prompt_manifest(project_dir)
    fragments = manifest.get("fragments", {})
    if not isinstance(fragments, dict):
        return ""
    raw_path = fragments.get("post_history_instructions", "prompts/post_history_instructions.md")
    return read_text(resolve_project_path(project_dir, str(raw_path))).strip()
