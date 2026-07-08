from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..character_catalog import (
    active_character_id,
    character_path,
    create_character,
    delete_character,
    load_character_catalog,
    purge_character,
    read_character,
    restore_character,
    set_active_character,
    trashed_characters,
    update_character_name,
    write_character,
)
from ..config import load_app_config
from ..conversation_store import load_recent_messages
from ..io_utils import read_json, read_text, write_json, write_text
from ..memory import load_memory, save_memory
from ..prompting import build_system_prompt, load_post_history_instructions


STATIC_DIR = Path(__file__).resolve().parent / "static"


def _read_prompt_files(project_dir: Path) -> dict[str, str]:
    manifest = read_json(project_dir / "config" / "prompt_manifest.json")
    prompts: dict[str, str] = {}
    system_template = str(manifest.get("systemTemplate", "prompts/system.md"))
    prompts["systemTemplate"] = read_text(project_dir / system_template)
    fragments = manifest.get("fragments", {})
    if isinstance(fragments, dict):
        for key, raw_path in fragments.items():
            prompts[str(key)] = read_text(project_dir / str(raw_path))
    return prompts


def _write_prompt_files(project_dir: Path, prompts: dict[str, Any]) -> None:
    manifest = read_json(project_dir / "config" / "prompt_manifest.json")
    if "systemTemplate" in prompts:
        write_text(project_dir / str(manifest.get("systemTemplate", "prompts/system.md")), str(prompts["systemTemplate"]))
    fragments = manifest.get("fragments", {})
    if isinstance(fragments, dict):
        for key, raw_path in fragments.items():
            if str(key) in prompts:
                write_text(project_dir / str(raw_path), str(prompts[str(key)]))


def read_config_payload(project_dir: Path, *, user_id: str = "preview") -> dict[str, Any]:
    character_id = active_character_id(project_dir)
    return {
        "app": read_json(project_dir / "config" / "app.json"),
        "modelProfiles": read_json(project_dir / "config" / "model_profiles.json"),
        "qqBot": read_json(project_dir / "config" / "qq_bot.json"),
        "commands": read_json(project_dir / "config" / "bot_commands.json"),
        "imageBridge": read_json(project_dir / "config" / "image_bridge.json"),
        "promptManifest": read_json(project_dir / "config" / "prompt_manifest.json"),
        "characterCatalog": load_character_catalog(project_dir),
        "characterTrash": trashed_characters(project_dir),
        "character": read_character(project_dir, character_id),
        "persona": read_json(project_dir / "personas" / "default.json"),
        "lorebook": read_json(project_dir / "lorebooks" / "default.json"),
        "events": read_json(project_dir / "events" / "active_events.json"),
        "prompts": _read_prompt_files(project_dir),
        "memory": load_memory(project_dir, user_id),
    }


def write_config_payload(project_dir: Path, payload: dict[str, Any], *, user_id: str = "preview") -> None:
    character_id = active_character_id(project_dir)
    json_targets = {
        "app": project_dir / "config" / "app.json",
        "modelProfiles": project_dir / "config" / "model_profiles.json",
        "qqBot": project_dir / "config" / "qq_bot.json",
        "commands": project_dir / "config" / "bot_commands.json",
        "imageBridge": project_dir / "config" / "image_bridge.json",
        "promptManifest": project_dir / "config" / "prompt_manifest.json",
        "character": character_path(project_dir, character_id),
        "persona": project_dir / "personas" / "default.json",
        "lorebook": project_dir / "lorebooks" / "default.json",
        "events": project_dir / "events" / "active_events.json",
    }
    for key, path in json_targets.items():
        if key in payload:
            value = payload[key]
            if not isinstance(value, dict):
                raise RuntimeError(f"{key} must be a JSON object.")
            if key == "character":
                normalized = write_character(project_dir, value)
                name = str(normalized.get("name", "") or "").strip()
                if name:
                    update_character_name(project_dir, character_id=character_id, name=name)
            else:
                write_json(path, value)
    if isinstance(payload.get("prompts"), dict):
        _write_prompt_files(project_dir, payload["prompts"])
    if isinstance(payload.get("memory"), dict):
        save_memory(project_dir, user_id, payload["memory"])


def build_prompt_preview(project_dir: Path, *, user_id: str, user_text: str) -> dict[str, Any]:
    app_config = load_app_config(project_dir)
    history = load_recent_messages(project_dir, user_id, limit=int(app_config.get("maxHistoryMessages", 24)))
    context_text = "\n".join([*(item["content"] for item in history), str(user_text or "")])
    memory_payload = load_memory(project_dir, user_id)
    memory_summary = str(memory_payload.get("summary", "")).strip()
    prompt_bundle = build_system_prompt(
        project_dir,
        user_id=user_id,
        memory_summary=memory_summary,
        context_text=context_text,
    )
    messages = [{"role": "system", "content": prompt_bundle.system_prompt}, *history]
    if str(user_text or "").strip():
        messages.append({"role": "user", "content": str(user_text).strip()})
    post_history = load_post_history_instructions(project_dir)
    if post_history:
        messages.append({"role": "system", "content": post_history})
    return {
        "messages": messages,
        "sourcePaths": prompt_bundle.source_paths,
    }


class ConfigUiHandler(BaseHTTPRequestHandler):
    project_dir: Path

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_bytes(self, body: bytes, *, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: Any, *, status: int = 200) -> None:
        self._send_bytes(
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            content_type="application/json; charset=utf-8",
            status=status,
        )

    def _read_body_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise RuntimeError("request body must be a JSON object.")
        return payload

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._serve_static("index.html")
            return
        if parsed.path.startswith("/static/"):
            self._serve_static(parsed.path.removeprefix("/static/"))
            return
        if parsed.path == "/api/config":
            user_id = parse_qs(parsed.query).get("userId", ["preview"])[0] or "preview"
            self._send_json(read_config_payload(self.project_dir, user_id=user_id))
            return
        if parsed.path == "/api/runtime":
            self._send_json(
                {
                    "serviceStatus": read_json(
                        self.project_dir / "runtime" / "service_state" / "qq_publish_outlet" / "latest_status.json",
                        default={},
                    ),
                    "latestUser": read_json(
                        self.project_dir / "runtime" / "qq_gateway" / "latest_user_openid.json",
                        default={},
                    ),
                }
            )
            return
        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/config":
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            user_id = parse_qs(parsed.query).get("userId", ["preview"])[0] or "preview"
            payload = self._read_body_json()
            write_config_payload(self.project_dir, payload, user_id=user_id)
            self._send_json({"ok": True, "characterCatalog": load_character_catalog(self.project_dir)})
        except Exception as exc:  # noqa: BLE001
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/characters":
            try:
                payload = self._read_body_json()
                action = str(payload.get("action", "") or "").strip()
                if action == "select":
                    catalog = set_active_character(self.project_dir, str(payload.get("characterId", "")))
                elif action == "create":
                    catalog = create_character(self.project_dir, name=str(payload.get("name", "") or ""))
                elif action == "duplicate":
                    catalog = create_character(
                        self.project_dir,
                        name=str(payload.get("name", "") or "角色副本"),
                        source_id=str(payload.get("characterId", "") or active_character_id(self.project_dir)),
                    )
                elif action == "rename":
                    catalog = update_character_name(
                        self.project_dir,
                        character_id=str(payload.get("characterId", "") or active_character_id(self.project_dir)),
                        name=str(payload.get("name", "") or ""),
                    )
                elif action == "delete":
                    catalog = delete_character(self.project_dir, str(payload.get("characterId", "")))
                elif action == "restore":
                    catalog = restore_character(self.project_dir, str(payload.get("characterId", "")))
                elif action == "purge":
                    catalog = purge_character(self.project_dir, str(payload.get("characterId", "")))
                else:
                    raise RuntimeError("unknown action.")
                catalog = load_character_catalog(self.project_dir)
                self._send_json(
                    {
                        "ok": True,
                        "characterCatalog": catalog,
                        "characterTrash": trashed_characters(self.project_dir),
                        "character": read_character(self.project_dir, active_character_id(self.project_dir)),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        if parsed.path != "/api/prompt-preview":
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self._read_body_json()
            preview = build_prompt_preview(
                self.project_dir,
                user_id=str(payload.get("userId", "preview") or "preview"),
                user_text=str(payload.get("userText", "") or ""),
            )
            self._send_json(preview)
        except Exception as exc:  # noqa: BLE001
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _serve_static(self, name: str) -> None:
        safe_name = str(name or "index.html").replace("\\", "/").strip("/")
        path = (STATIC_DIR / safe_name).resolve()
        if STATIC_DIR.resolve() not in path.parents and path != STATIC_DIR.resolve():
            self._send_json({"error": "invalid path"}, status=HTTPStatus.BAD_REQUEST)
            return
        if not path.exists() or not path.is_file():
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        suffix = path.suffix.lower()
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
        }.get(suffix, "application/octet-stream")
        self._send_bytes(path.read_bytes(), content_type=content_type)


def run_config_ui(project_dir: Path, *, host: str, port: int) -> None:
    handler_class = type("ProjectConfigUiHandler", (ConfigUiHandler,), {"project_dir": project_dir})
    server = ThreadingHTTPServer((host, int(port)), handler_class)
    print(f"[config-ui] http://{host}:{int(port)}", flush=True)
    server.serve_forever()
