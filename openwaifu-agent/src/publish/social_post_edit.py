from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import read_json, write_json


OVERRIDE_FILENAME = "social_post_override.json"
MAX_SOCIAL_POST_TEXT_CHARS = 5000


def social_post_override_path(run_dir: Path) -> Path:
    return Path(run_dir).resolve() / "publish" / OVERRIDE_FILENAME


def normalize_social_post_text(value: Any) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) > MAX_SOCIAL_POST_TEXT_CHARS:
        raise RuntimeError(f"社媒文案不能超过 {MAX_SOCIAL_POST_TEXT_CHARS} 个字符。")
    return text


def _read_json_object(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = read_json(path)
    return payload if isinstance(payload, dict) else None


def _read_generated_social_post_text(run_dir: Path) -> str:
    package_payload = _read_json_object(run_dir / "social_post" / "01_social_post_package.json")
    if package_payload is not None:
        text = normalize_social_post_text(package_payload.get("socialPostText", ""))
        if text:
            return text
    summary_payload = _read_json_object(run_dir / "output" / "run_summary.json")
    if summary_payload is not None:
        generated_text = normalize_social_post_text(summary_payload.get("generatedSocialPostText", ""))
        if generated_text:
            return generated_text
        return normalize_social_post_text(summary_payload.get("socialPostText", ""))
    return ""


def read_social_post_override(run_dir: Path) -> dict[str, Any] | None:
    path = social_post_override_path(run_dir)
    payload = _read_json_object(path)
    if payload is None:
        return None
    text = normalize_social_post_text(payload.get("socialPostText", ""))
    if not text:
        return None
    return {
        "socialPostText": text,
        "updatedAt": str(payload.get("updatedAt", "")).strip(),
        "source": str(payload.get("source", "")).strip(),
        "path": str(path),
    }


def read_effective_social_post(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir).resolve()
    generated_text = _read_generated_social_post_text(run_dir)
    override = read_social_post_override(run_dir)
    effective_text = override["socialPostText"] if override else generated_text
    return {
        "runId": run_dir.name,
        "socialPostText": effective_text,
        "generatedSocialPostText": generated_text,
        "manualSocialPostText": override["socialPostText"] if override else "",
        "isManual": override is not None,
        "updatedAt": override["updatedAt"] if override else "",
        "overridePath": override["path"] if override else "",
        "maxLength": MAX_SOCIAL_POST_TEXT_CHARS,
    }


def apply_effective_social_post_package(run_dir: Path, social_post_package: dict[str, Any]) -> dict[str, Any]:
    effective = dict(social_post_package)
    state = read_effective_social_post(run_dir)
    text = normalize_social_post_text(state.get("socialPostText", ""))
    if text:
        effective["socialPostText"] = text
    if state.get("isManual"):
        effective["manualSocialPostOverride"] = {
            "updatedAt": state.get("updatedAt", ""),
            "path": state.get("overridePath", ""),
        }
    return effective


def _update_run_summary_social_post(run_dir: Path, state: dict[str, Any]) -> None:
    summary_path = Path(run_dir).resolve() / "output" / "run_summary.json"
    summary_payload = _read_json_object(summary_path) or {"runId": Path(run_dir).name}
    if "generatedSocialPostText" not in summary_payload:
        summary_payload["generatedSocialPostText"] = state["generatedSocialPostText"]
    summary_payload["socialPostText"] = state["socialPostText"]
    summary_payload["manualSocialPostText"] = state["manualSocialPostText"]
    summary_payload["manualSocialPostUpdatedAt"] = state["updatedAt"]
    summary_payload["manualSocialPostOverridePath"] = state["overridePath"]
    write_json(summary_path, summary_payload)


def save_social_post_override(run_dir: Path, text: Any, *, source: str = "workbench") -> dict[str, Any]:
    run_dir = Path(run_dir).resolve()
    normalized_text = normalize_social_post_text(text)
    if not normalized_text:
        raise RuntimeError("社媒文案不能为空。")
    path = social_post_override_path(run_dir)
    payload = {
        "runId": run_dir.name,
        "socialPostText": normalized_text,
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": str(source or "workbench").strip() or "workbench",
    }
    write_json(path, payload)
    state = read_effective_social_post(run_dir)
    _update_run_summary_social_post(run_dir, state)
    return state
