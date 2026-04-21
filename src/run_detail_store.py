from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from io_utils import normalize_spaces
from runtime_layout import runs_root


DEFAULT_DETAIL_TEXT_LIMIT = 40000


def _safe_read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _resolve_generated_image_from_summary(run_dir: Path, summary_payload: dict[str, Any]) -> Path | None:
    generated_image_path = normalize_spaces(str(summary_payload.get("generatedImagePath", "")))
    if not generated_image_path:
        return None
    image_path = Path(generated_image_path).resolve()
    try:
        image_path.relative_to(run_dir.resolve())
    except ValueError:
        return None
    if not image_path.exists() or not image_path.is_file():
        return None
    if image_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        return None
    return image_path


def _read_text_excerpt(path: Path, *, char_limit: int = DEFAULT_DETAIL_TEXT_LIMIT) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "exists": path.exists(),
        "path": str(path),
        "text": "",
        "truncated": False,
        "error": "",
    }
    if not path.exists():
        return snapshot
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            text = handle.read(max(int(char_limit), 1) + 1)
    except OSError as exc:
        snapshot["error"] = str(exc)
        return snapshot
    if len(text) > max(int(char_limit), 1):
        text = text[: max(int(char_limit), 1)].rstrip() + "\n\n[内容过长，面板已截断显示]"
        snapshot["truncated"] = True
    snapshot["text"] = text.strip()
    return snapshot


def _read_json_document(path: Path, *, char_limit: int = DEFAULT_DETAIL_TEXT_LIMIT) -> dict[str, Any]:
    text_snapshot = _read_text_excerpt(path, char_limit=char_limit)
    document: dict[str, Any] = {
        "exists": bool(text_snapshot["exists"]),
        "path": str(path),
        "payload": None,
        "rawText": str(text_snapshot["text"]),
        "truncated": bool(text_snapshot["truncated"]),
        "error": str(text_snapshot["error"]),
    }
    if not text_snapshot["exists"] or text_snapshot["error"]:
        return document
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        document["error"] = "JSON 解析失败，已回退为原始文本显示。"
        return document
    if not isinstance(payload, dict):
        document["error"] = "JSON 顶层不是对象，已按原始文本显示。"
        return document
    raw_text = json.dumps(payload, ensure_ascii=False, indent=2)
    if len(raw_text) > max(int(char_limit), 1):
        raw_text = raw_text[: max(int(char_limit), 1)].rstrip() + "\n\n[内容过长，面板已截断显示]"
        document["truncated"] = True
    document["payload"] = payload
    document["rawText"] = raw_text
    return document


def _section_payload(
    *,
    section_id: str,
    title: str,
    path: Path,
    body_text: str,
    raw_text: str,
    exists: bool,
    meta_rows: list[dict[str, str]] | None = None,
    bullets: list[str] | None = None,
    compare_blocks: list[dict[str, Any]] | None = None,
    error: str = "",
    truncated: bool = False,
) -> dict[str, Any]:
    return {
        "id": section_id,
        "title": title,
        "path": str(path),
        "exists": bool(exists),
        "bodyText": body_text.strip(),
        "rawText": raw_text.strip(),
        "metaRows": meta_rows or [],
        "bullets": bullets or [],
        "compareBlocks": compare_blocks or [],
        "error": normalize_spaces(error),
        "truncated": bool(truncated),
    }


def _split_prompt_tags(prompt: str) -> list[str]:
    normalized = normalize_spaces(prompt)
    if not normalized:
        return []
    parts = [normalize_spaces(part) for part in re.split(r"\s*,\s*", normalized) if normalize_spaces(part)]
    return parts


def _build_prompt_diff_segments(before_prompt: str, after_prompt: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    before_tags = _split_prompt_tags(before_prompt)
    after_tags = _split_prompt_tags(after_prompt)
    matcher = SequenceMatcher(a=before_tags, b=after_tags)
    before_segments: list[dict[str, Any]] = []
    after_segments: list[dict[str, Any]] = []
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        before_chunk = ", ".join(before_tags[i1:i2]).strip()
        after_chunk = ", ".join(after_tags[j1:j2]).strip()
        changed = opcode != "equal"
        if before_chunk:
            before_segments.append({"text": before_chunk, "changed": changed})
        if after_chunk:
            after_segments.append({"text": after_chunk, "changed": changed})
    return before_segments, after_segments


def _build_sampling_section(path: Path) -> dict[str, Any]:
    document = _read_json_document(path)
    payload = document["payload"] if isinstance(document.get("payload"), dict) else {}
    sample_payload = payload.get("socialSignalSample") if isinstance(payload.get("socialSignalSample"), dict) else {}
    signals = [
        normalize_spaces(str(item))
        for item in (sample_payload.get("sampledSignalsZh", []) or [])
        if normalize_spaces(str(item))
    ]
    meta_rows = []
    if sample_payload:
        meta_rows.extend(
            [
                {"label": "来源", "value": normalize_spaces(str(sample_payload.get("sourceZh", ""))) or "未记录"},
                {"label": "分区", "value": normalize_spaces(str(sample_payload.get("providerZh", ""))) or "未记录"},
            ]
        )
    body_text = "\n\n".join(signals) if signals else ""
    if document["exists"] and not body_text and not document["error"]:
        body_text = "文件存在，但没有解析出 socialSignalSample。"
    raw_source = sample_payload if sample_payload else payload
    raw_text = (
        json.dumps(raw_source, ensure_ascii=False, indent=2)
        if isinstance(raw_source, dict) and raw_source
        else str(document["rawText"])
    )
    return _section_payload(
        section_id="sampling-input",
        title="采样原始内容",
        path=path,
        body_text=body_text,
        raw_text=raw_text,
        exists=bool(document["exists"]),
        meta_rows=meta_rows,
        bullets=signals,
        error=str(document["error"]),
        truncated=bool(document["truncated"]),
    )


def _build_world_design_section(path: Path) -> dict[str, Any]:
    document = _read_json_document(path)
    payload = document["payload"] if isinstance(document.get("payload"), dict) else {}
    scene_premise = normalize_spaces(str(payload.get("scenePremiseZh", "")))
    world_scene = normalize_spaces(str(payload.get("worldSceneZh", "")))
    meta_rows = [{"label": "场景标题", "value": scene_premise or "未记录"}] if document["exists"] else []
    body_text = world_scene or "文件存在，但没有解析出 worldSceneZh。"
    return _section_payload(
        section_id="world-design",
        title="场景设计稿",
        path=path,
        body_text=body_text if document["exists"] else "",
        raw_text=str(document["rawText"]),
        exists=bool(document["exists"]),
        meta_rows=meta_rows,
        error=str(document["error"]),
        truncated=bool(document["truncated"]),
    )


def _build_text_section(section_id: str, title: str, path: Path) -> dict[str, Any]:
    text_snapshot = _read_text_excerpt(path)
    return _section_payload(
        section_id=section_id,
        title=title,
        path=path,
        body_text=str(text_snapshot["text"]),
        raw_text=str(text_snapshot["text"]),
        exists=bool(text_snapshot["exists"]),
        error=str(text_snapshot["error"]),
        truncated=bool(text_snapshot["truncated"]),
    )


def _relative_run_path(run_dir: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(run_dir.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _build_final_prompt_section(run_dir: Path) -> dict[str, Any]:
    prompt_guard_package_path = run_dir / "prompt_guard" / "02_prompt_package.json"
    prompt_package_path = run_dir / "prompt_builder" / "01_prompt_package.json"
    image_prompt_path = run_dir / "prompt_builder" / "00_image_prompt.json"
    if prompt_guard_package_path.exists():
        source_path = prompt_guard_package_path
    elif prompt_package_path.exists():
        source_path = prompt_package_path
    else:
        source_path = image_prompt_path
    document = _read_json_document(source_path)
    payload = document["payload"] if isinstance(document.get("payload"), dict) else {}
    positive_prompt = normalize_spaces(str(payload.get("positivePrompt", payload.get("positive", ""))))
    negative_prompt = normalize_spaces(str(payload.get("negativePrompt", payload.get("negative", ""))))
    meta_rows = []
    meta_payload = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    if meta_payload:
        created_at = normalize_spaces(str(meta_payload.get("createdAt", "")))
        run_mode = normalize_spaces(str(meta_payload.get("runMode", "")))
        if created_at:
            meta_rows.append({"label": "生成时间", "value": created_at})
        if run_mode:
            meta_rows.append({"label": "运行模式", "value": run_mode})
    review_status = normalize_spaces(str(payload.get("reviewStatus", "")))
    if review_status:
        meta_rows.append({"label": "回调状态", "value": review_status})
    if "promptChanged" in payload:
        meta_rows.append({"label": "是否修改", "value": "是" if bool(payload.get("promptChanged")) else "否"})
    if positive_prompt:
        meta_rows.append({"label": "正向长度", "value": str(len(positive_prompt))})
    if negative_prompt:
        meta_rows.append({"label": "负向长度", "value": str(len(negative_prompt))})
    if source_path.exists():
        meta_rows.append({"label": "保存路径", "value": _relative_run_path(run_dir, source_path)})
    body_parts: list[str] = []
    if positive_prompt:
        body_parts.append(f"正向 Prompt\n{positive_prompt}")
    if negative_prompt:
        body_parts.append(f"负向 Prompt\n{negative_prompt}")
    body_text = "\n\n".join(body_parts)
    if document["exists"] and not body_text and not document["error"]:
        body_text = "文件存在，但没有解析出正向或负向 Prompt。"
    return _section_payload(
        section_id="image-prompt",
        title="最终生图 Prompt",
        path=source_path,
        body_text=body_text,
        raw_text=str(document["rawText"]),
        exists=bool(document["exists"]),
        meta_rows=meta_rows,
        error=str(document["error"]),
        truncated=bool(document["truncated"]),
    )


def _build_prompt_comparison_section(run_dir: Path) -> dict[str, Any]:
    builder_path = run_dir / "prompt_builder" / "01_prompt_package.json"
    guarded_path = run_dir / "prompt_guard" / "02_prompt_package.json"
    builder_document = _read_json_document(builder_path)
    guarded_document = _read_json_document(guarded_path)
    builder_payload = builder_document["payload"] if isinstance(builder_document.get("payload"), dict) else {}
    guarded_payload = guarded_document["payload"] if isinstance(guarded_document.get("payload"), dict) else {}

    before_positive = str(builder_payload.get("positivePrompt", builder_payload.get("positive", ""))).strip()
    before_negative = str(builder_payload.get("negativePrompt", builder_payload.get("negative", ""))).strip()
    after_positive = str(guarded_payload.get("positivePrompt", guarded_payload.get("positive", ""))).strip()
    after_negative = str(guarded_payload.get("negativePrompt", guarded_payload.get("negative", ""))).strip()

    meta_rows: list[dict[str, str]] = []
    if builder_document["exists"]:
        meta_rows.append({"label": "回调前路径", "value": _relative_run_path(run_dir, builder_path)})
    if guarded_document["exists"]:
        meta_rows.append({"label": "回调后路径", "value": _relative_run_path(run_dir, guarded_path)})
    if "promptChanged" in guarded_payload:
        meta_rows.append({"label": "是否修改", "value": "是" if bool(guarded_payload.get("promptChanged")) else "否"})
    if before_positive:
        meta_rows.append({"label": "回调前正向长度", "value": str(len(before_positive))})
    if after_positive:
        meta_rows.append({"label": "回调后正向长度", "value": str(len(after_positive))})
    if before_negative:
        meta_rows.append({"label": "回调前负向长度", "value": str(len(before_negative))})
    if after_negative:
        meta_rows.append({"label": "回调后负向长度", "value": str(len(after_negative))})

    compare_blocks: list[dict[str, Any]] = []
    before_positive_segments, after_positive_segments = _build_prompt_diff_segments(before_positive, after_positive)
    before_negative_segments, after_negative_segments = _build_prompt_diff_segments(before_negative, after_negative)
    if before_positive or after_positive:
        compare_blocks.extend(
            [
                {"title": "回调前 正向 Prompt", "variant": "before", "segments": before_positive_segments},
                {"title": "回调后 正向 Prompt", "variant": "after", "segments": after_positive_segments},
            ]
        )
    if before_negative or after_negative:
        compare_blocks.extend(
            [
                {"title": "回调前 负向 Prompt", "variant": "before", "segments": before_negative_segments},
                {"title": "回调后 负向 Prompt", "variant": "after", "segments": after_negative_segments},
            ]
        )

    body_text = ""
    if not body_text and (builder_document["exists"] or guarded_document["exists"]):
        if not compare_blocks:
            body_text = "已找到 Prompt package，但没有解析出可比较的回调前后 Prompt。"

    comparison_payload = {
        "before": {
            "path": str(builder_path),
            "exists": bool(builder_document["exists"]),
            "positivePrompt": before_positive,
            "negativePrompt": before_negative,
        },
        "after": {
            "path": str(guarded_path),
            "exists": bool(guarded_document["exists"]),
            "positivePrompt": after_positive,
            "negativePrompt": after_negative,
            "reviewStatus": str(guarded_payload.get("reviewStatus", "")).strip(),
            "promptChanged": bool(guarded_payload.get("promptChanged", False)),
        },
    }
    error_parts = [
        normalize_spaces(str(builder_document.get("error", ""))),
        normalize_spaces(str(guarded_document.get("error", ""))),
    ]
    return _section_payload(
        section_id="prompt-guard-compare",
        title="Prompt 回调前后对比",
        path=(
            f"{_relative_run_path(run_dir, builder_path)} -> {_relative_run_path(run_dir, guarded_path)}"
            if builder_document["exists"] or guarded_document["exists"]
            else str(guarded_path)
        ),
        body_text=body_text,
        raw_text=json.dumps(comparison_payload, ensure_ascii=False, indent=2),
        exists=bool(builder_document["exists"] or guarded_document["exists"]),
        meta_rows=meta_rows,
        compare_blocks=compare_blocks,
        error=" | ".join([item for item in error_parts if item]),
        truncated=False,
    )


def _build_prompt_guard_review_section(run_dir: Path) -> dict[str, Any]:
    review_report_path = run_dir / "prompt_guard" / "01_review_report.json"
    document = _read_json_document(review_report_path)
    payload = document["payload"] if isinstance(document.get("payload"), dict) else {}
    issues = [
        normalize_spaces(str(item))
        for item in (payload.get("issues", []) or [])
        if normalize_spaces(str(item))
    ]
    meta_rows = []
    review_status = normalize_spaces(str(payload.get("status", "")))
    if review_status:
        meta_rows.append({"label": "回调状态", "value": review_status})
    if "changed" in payload:
        meta_rows.append({"label": "是否修改", "value": "是" if bool(payload.get("changed")) else "否"})
    change_summary = normalize_spaces(str(payload.get("changeSummary", "")))
    body_text = change_summary
    if not body_text and document["exists"] and not document["error"]:
        body_text = "文件存在，但没有解析出回调摘要。"
    return _section_payload(
        section_id="prompt-guard-review",
        title="Prompt 回调报告",
        path=review_report_path,
        body_text=body_text if document["exists"] else "",
        raw_text=str(document["rawText"]),
        exists=bool(document["exists"]),
        meta_rows=meta_rows,
        bullets=issues,
        error=str(document["error"]),
        truncated=bool(document["truncated"]),
    )

def _resolve_run_dir_from_run_id(project_dir: Path, run_id: str) -> Path | None:
    normalized_run_id = normalize_spaces(run_id)
    if not normalized_run_id:
        return None
    run_dir = (runs_root(project_dir) / normalized_run_id).resolve()
    try:
        run_dir.relative_to(runs_root(project_dir).resolve())
    except ValueError:
        return None
    if not run_dir.exists() or not run_dir.is_dir():
        return None
    return run_dir


def _looks_like_run_dir(path: Path) -> bool:
    return bool(
        path.exists()
        and path.is_dir()
        and (
            (path / "creative").is_dir()
            or (path / "prompt_builder").is_dir()
            or (path / "prompt_guard").is_dir()
            or (path / "output" / "run_summary.json").is_file()
        )
    )


def _resolve_run_dir_from_review_path(project_dir: Path, raw_path: str) -> Path | None:
    normalized_path = normalize_spaces(raw_path)
    if not normalized_path:
        return None
    candidate = Path(normalized_path)
    candidate = (project_dir / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if not candidate.exists():
        return None
    current = candidate if candidate.is_dir() else candidate.parent
    for path in (current, *current.parents):
        if path.name == "creative" and _looks_like_run_dir(path.parent):
            return path.parent
        if path.name in {"prompt_builder", "prompt_guard", "output", "execution", "social_post", "publish"} and _looks_like_run_dir(path.parent):
            return path.parent
        if _looks_like_run_dir(path):
            return path
    return None


def resolve_generated_image_artifact(project_dir: Path, run_id: str) -> Path | None:
    run_dir = _resolve_run_dir_from_run_id(project_dir, run_id)
    if run_dir is None:
        return None
    summary_payload = _safe_read_json(run_dir / "output" / "run_summary.json")
    if summary_payload is None:
        return None
    return _resolve_generated_image_from_summary(run_dir, summary_payload)


def _build_run_detail_snapshot_from_run_dir(
    project_dir: Path,
    run_dir: Path,
    *,
    run_id_hint: str = "",
) -> dict[str, Any]:
    project_dir = Path(project_dir).resolve()
    run_dir = Path(run_dir).resolve()
    creative_dir = run_dir / "creative"
    summary_document = _read_json_document(run_dir / "output" / "run_summary.json")
    summary_payload = summary_document["payload"] if isinstance(summary_document.get("payload"), dict) else {}
    resolved_image_path = (
        _resolve_generated_image_from_summary(run_dir, summary_payload)
        if isinstance(summary_payload, dict)
        else None
    )
    sections = [
        _build_sampling_section(creative_dir / "01_world_design_input.json"),
        _build_world_design_section(creative_dir / "01_world_design.json"),
        _build_text_section("environment-design", "环境设计稿", creative_dir / "02_environment_design.md"),
        _build_text_section("styling-design", "造型设计稿", creative_dir / "03_styling_design.md"),
        _build_text_section("action-design", "动作设计稿", creative_dir / "04_action_design.md"),
        _build_final_prompt_section(run_dir),
        _build_prompt_comparison_section(run_dir),
        _build_prompt_guard_review_section(run_dir),
    ]
    available_count = sum(1 for item in sections if item["exists"])
    effective_run_id = normalize_spaces(str(summary_payload.get("runId", ""))) or normalize_spaces(run_id_hint) or run_dir.name
    detail_title = (
        normalize_spaces(str(summary_payload.get("sceneDraftPremiseZh", "")))
        or next((row["value"] for row in sections[1]["metaRows"] if row.get("label") == "场景标题"), "")
        or effective_run_id
    )
    social_post_text = normalize_spaces(str(summary_payload.get("socialPostText", "")))
    publish_receipts = (
        summary_payload.get("publishReceipts", [])
        if isinstance(summary_payload.get("publishReceipts", []), list)
        else []
    )
    first_receipt = publish_receipts[0] if publish_receipts and isinstance(publish_receipts[0], dict) else {}
    route_run_id = ""
    try:
        run_dir.relative_to(runs_root(project_dir).resolve())
        route_run_id = run_dir.name
    except ValueError:
        route_run_id = ""
    return {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "projectDir": str(project_dir),
        "runId": effective_run_id,
        "runRoot": str(run_dir),
        "detailTitle": detail_title,
        "summaryPath": str(run_dir / "output" / "run_summary.json"),
        "sceneDraftPremiseZh": normalize_spaces(str(summary_payload.get("sceneDraftPremiseZh", ""))),
        "socialPostPreview": normalize_spaces(social_post_text),
        "generatedImagePath": str(resolved_image_path) if resolved_image_path else "",
        "imageRoute": (
            f"/artifacts/generated-image?runId={quote(route_run_id, safe='')}"
            if resolved_image_path and route_run_id
            else ""
        ),
        "publishStatus": normalize_spaces(str(first_receipt.get("status", ""))),
        "publishedAt": normalize_spaces(str(first_receipt.get("publishedAt", ""))),
        "sectionCounts": {
            "total": len(sections),
            "available": available_count,
            "missing": len(sections) - available_count,
        },
        "sections": sections,
        "summaryRawText": str(summary_document["rawText"]),
        "summaryError": str(summary_document["error"]),
        "summaryTruncated": bool(summary_document["truncated"]),
    }


def build_run_detail_snapshot(project_dir: Path, run_id: str) -> dict[str, Any] | None:
    run_dir = _resolve_run_dir_from_run_id(project_dir, run_id)
    if run_dir is None:
        return None
    return _build_run_detail_snapshot_from_run_dir(project_dir, run_dir, run_id_hint=normalize_spaces(run_id))


def build_run_detail_snapshot_from_path(project_dir: Path, path_text: str) -> dict[str, Any] | None:
    run_dir = _resolve_run_dir_from_review_path(project_dir, path_text)
    if run_dir is None:
        return None
    return _build_run_detail_snapshot_from_run_dir(project_dir, run_dir, run_id_hint=run_dir.name)
