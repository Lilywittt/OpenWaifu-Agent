from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from character_assets import load_character_assets
from creative import (
    build_default_run_context,
    run_parallel_design_stages,
    run_world_design_stage,
)
from execution import run_execution_pipeline
from generation_slot import occupy_generation_slot
from io_utils import normalize_spaces, read_json, write_json, write_text
from model_profiles import resolve_creative_model_config_path, resolve_prompt_guard_model_config_path
from prompt_builder import run_prompt_builder_pipeline
from prompt_guard import run_prompt_guard_pipeline
from publish.qq_bot_scene_draft import parse_scene_draft_message
from runtime_layout import create_run_bundle
from social_post import run_social_post_pipeline


SOURCE_KIND_SCENE_DRAFT_TEXT = "scene_draft_text"
SOURCE_KIND_SCENE_DRAFT_FILE = "scene_draft_file"
SOURCE_KIND_LIVE_SAMPLING = "live_sampling"
SOURCE_KIND_SAMPLE_TEXT = "sample_text"
SOURCE_KIND_SAMPLE_FILE = "sample_file"
SOURCE_KIND_CREATIVE_PACKAGE_TEXT = "creative_package_text"
SOURCE_KIND_CREATIVE_PACKAGE_FILE = "creative_package_file"
SOURCE_KIND_PROMPT_PACKAGE_TEXT = "prompt_package_text"
SOURCE_KIND_PROMPT_PACKAGE_FILE = "prompt_package_file"

END_STAGE_SCENE_DRAFT = "scene_draft"
END_STAGE_DESIGN = "design"
END_STAGE_SOCIAL_POST = "social_post"
END_STAGE_PROMPT = "prompt"
END_STAGE_IMAGE = "image"

SOURCE_KIND_LABELS = {
    SOURCE_KIND_SCENE_DRAFT_TEXT: "场景稿文本或 JSON",
    SOURCE_KIND_SCENE_DRAFT_FILE: "已有场景稿文件",
    SOURCE_KIND_LIVE_SAMPLING: "实时采样全链路",
    SOURCE_KIND_SAMPLE_TEXT: "采样内容正文",
    SOURCE_KIND_SAMPLE_FILE: "已有采样输入文件",
    SOURCE_KIND_CREATIVE_PACKAGE_TEXT: "creative package 正文",
    SOURCE_KIND_CREATIVE_PACKAGE_FILE: "已有 creative package",
    SOURCE_KIND_PROMPT_PACKAGE_TEXT: "prompt package 正文",
    SOURCE_KIND_PROMPT_PACKAGE_FILE: "已有 prompt package",
}

END_STAGE_LABELS = {
    END_STAGE_SCENE_DRAFT: "场景稿",
    END_STAGE_DESIGN: "三份设计稿",
    END_STAGE_SOCIAL_POST: "社媒文案",
    END_STAGE_PROMPT: "最终 Prompt",
    END_STAGE_IMAGE: "生图",
}

SOURCE_ALLOWED_END_STAGES = {
    SOURCE_KIND_SCENE_DRAFT_TEXT: (
        END_STAGE_SCENE_DRAFT,
        END_STAGE_DESIGN,
        END_STAGE_SOCIAL_POST,
        END_STAGE_PROMPT,
        END_STAGE_IMAGE,
    ),
    SOURCE_KIND_SCENE_DRAFT_FILE: (
        END_STAGE_SCENE_DRAFT,
        END_STAGE_DESIGN,
        END_STAGE_SOCIAL_POST,
        END_STAGE_PROMPT,
        END_STAGE_IMAGE,
    ),
    SOURCE_KIND_LIVE_SAMPLING: (
        END_STAGE_IMAGE,
    ),
    SOURCE_KIND_SAMPLE_TEXT: (
        END_STAGE_SCENE_DRAFT,
        END_STAGE_DESIGN,
        END_STAGE_SOCIAL_POST,
        END_STAGE_PROMPT,
        END_STAGE_IMAGE,
    ),
    SOURCE_KIND_SAMPLE_FILE: (
        END_STAGE_SCENE_DRAFT,
        END_STAGE_DESIGN,
        END_STAGE_SOCIAL_POST,
        END_STAGE_PROMPT,
        END_STAGE_IMAGE,
    ),
    SOURCE_KIND_CREATIVE_PACKAGE_TEXT: (
        END_STAGE_SOCIAL_POST,
        END_STAGE_PROMPT,
        END_STAGE_IMAGE,
    ),
    SOURCE_KIND_CREATIVE_PACKAGE_FILE: (
        END_STAGE_SOCIAL_POST,
        END_STAGE_PROMPT,
        END_STAGE_IMAGE,
    ),
    SOURCE_KIND_PROMPT_PACKAGE_TEXT: (
        END_STAGE_IMAGE,
    ),
    SOURCE_KIND_PROMPT_PACKAGE_FILE: (
        END_STAGE_IMAGE,
    ),
}

SOURCE_KIND_HINTS = {
    SOURCE_KIND_SCENE_DRAFT_TEXT: "直接贴场景稿正文，或贴 scenePremiseZh/worldSceneZh JSON。",
    SOURCE_KIND_SCENE_DRAFT_FILE: "填写 01_world_design.json，或填写包含该文件的 run/creative 目录。",
    SOURCE_KIND_LIVE_SAMPLING: "不需要填写输入，工作台会直接从实时采样开始跑完整生成链。",
    SOURCE_KIND_SAMPLE_TEXT: "直接写采样内容，每行一条即可；如果你手里已有 JSON，也可以直接贴 JSON。",
    SOURCE_KIND_SAMPLE_FILE: "填写 01_world_design_input.json，或填写包含该文件的 run/creative 目录。",
    SOURCE_KIND_CREATIVE_PACKAGE_TEXT: "直接填写场景与设计稿正文，工作台会自动封装成 creative package。",
    SOURCE_KIND_CREATIVE_PACKAGE_FILE: "填写 05_creative_package.json，或填写包含该文件的 run/creative 目录。",
    SOURCE_KIND_PROMPT_PACKAGE_TEXT: "直接填写正向与负向 Prompt，工作台会自动封装成 prompt package。",
    SOURCE_KIND_PROMPT_PACKAGE_FILE: "填写 prompt_builder/01_prompt_package.json 或 prompt_guard/02_prompt_package.json。",
}

_SOURCE_RESOLUTION_RULES = {
    SOURCE_KIND_SCENE_DRAFT_FILE: (
        "01_world_design.json",
        ["creative/01_world_design.json", "01_world_design.json"],
    ),
    SOURCE_KIND_SAMPLE_FILE: (
        "01_world_design_input.json",
        ["creative/01_world_design_input.json", "01_world_design_input.json"],
    ),
    SOURCE_KIND_CREATIVE_PACKAGE_FILE: (
        "05_creative_package.json",
        ["creative/05_creative_package.json", "05_creative_package.json"],
    ),
    SOURCE_KIND_PROMPT_PACKAGE_FILE: (
        "",
        [
            "prompt_guard/02_prompt_package.json",
            "prompt_builder/01_prompt_package.json",
            "02_prompt_package.json",
            "01_prompt_package.json",
        ],
    ),
}


def _maybe_abort(should_abort: Callable[[], bool] | None) -> None:
    if should_abort is not None and should_abort():
        raise InterruptedError("Content workbench task interrupted.")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _resolve_stage_file(source: str, *, expected_filename: str, relative_candidates: list[str]) -> Path:
    path = Path(str(source or "").strip()).resolve()
    if path.is_file():
        if expected_filename and path.name != expected_filename:
            raise RuntimeError(f"Unsupported source file: {path}")
        return path
    for relative_path in relative_candidates:
        candidate = path / relative_path
        if candidate.exists():
            return candidate.resolve()
    display_name = expected_filename or "supported workbench source file"
    raise RuntimeError(f"Could not find {display_name} under source: {path}")


def resolve_source_path(source_kind: str, source: str) -> Path:
    expected_filename, relative_candidates = _SOURCE_RESOLUTION_RULES[source_kind]
    return _resolve_stage_file(
        source,
        expected_filename=expected_filename,
        relative_candidates=relative_candidates,
    )


def validate_workbench_request(project_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    source_kind = _normalize_text(payload.get("sourceKind"))
    if source_kind not in SOURCE_KIND_LABELS:
        raise RuntimeError(f"Unsupported sourceKind: {source_kind or '<empty>'}")

    end_stage = _normalize_text(payload.get("endStage"))
    if end_stage not in END_STAGE_LABELS:
        raise RuntimeError(f"Unsupported endStage: {end_stage or '<empty>'}")
    if end_stage not in SOURCE_ALLOWED_END_STAGES[source_kind]:
        raise RuntimeError(
            f"{SOURCE_KIND_LABELS[source_kind]} cannot stop at {END_STAGE_LABELS.get(end_stage, end_stage)}."
        )

    label = normalize_spaces(str(payload.get("label", ""))) or SOURCE_KIND_LABELS[source_kind]
    normalized: dict[str, Any] = {
        "sourceKind": source_kind,
        "endStage": end_stage,
        "label": label,
    }
    request_id = _normalize_text(payload.get("requestId"))
    if request_id:
        normalized["requestId"] = request_id
    if source_kind == SOURCE_KIND_SCENE_DRAFT_TEXT:
        scene_draft_text = str(payload.get("sceneDraftText", "")).strip()
        if not scene_draft_text:
            raise RuntimeError("Scene draft text cannot be empty.")
        normalized["sceneDraftText"] = scene_draft_text
        return normalized

    if source_kind == SOURCE_KIND_LIVE_SAMPLING:
        return normalized

    if source_kind == SOURCE_KIND_SAMPLE_TEXT:
        source_content = str(payload.get("sourceContent", "")).strip()
        if not source_content:
            raise RuntimeError("Sample content cannot be empty.")
        normalized["sourceContent"] = source_content
        return normalized

    if source_kind == SOURCE_KIND_CREATIVE_PACKAGE_TEXT:
        world_scene_text = str(payload.get("worldSceneText", "")).strip()
        if not world_scene_text:
            raise RuntimeError("Creative package content must include world scene text.")
        normalized["scenePremiseText"] = str(payload.get("scenePremiseText", "")).strip()
        normalized["worldSceneText"] = world_scene_text
        normalized["environmentDesignText"] = str(payload.get("environmentDesignText", "")).strip()
        normalized["stylingDesignText"] = str(payload.get("stylingDesignText", "")).strip()
        normalized["actionDesignText"] = str(payload.get("actionDesignText", "")).strip()
        return normalized

    if source_kind == SOURCE_KIND_PROMPT_PACKAGE_TEXT:
        positive_prompt_text = str(payload.get("positivePromptText", "")).strip()
        negative_prompt_text = str(payload.get("negativePromptText", "")).strip()
        if not positive_prompt_text:
            raise RuntimeError("Positive prompt text cannot be empty.")
        if not negative_prompt_text:
            raise RuntimeError("Negative prompt text cannot be empty.")
        normalized["positivePromptText"] = positive_prompt_text
        normalized["negativePromptText"] = negative_prompt_text
        return normalized

    source_path = _normalize_text(payload.get("sourcePath"))
    if not source_path:
        raise RuntimeError("Source path cannot be empty.")
    resolved_source_path = resolve_source_path(source_kind, source_path)
    normalized["sourcePath"] = str(resolved_source_path)
    return normalized


def _write_markdown_if_present(path: Path, content: str) -> None:
    text = str(content or "").strip()
    if text:
        write_text(path, text + "\n")


def materialize_creative_snapshot(bundle, creative_package: dict[str, Any]) -> None:
    social_signal_sample = creative_package.get("socialSignalSample")
    if isinstance(social_signal_sample, dict) and social_signal_sample:
        write_json(bundle.creative_dir / "01_world_design_input.json", {"socialSignalSample": social_signal_sample})
        write_json(bundle.creative_dir / "00_social_signal_filter.json", social_signal_sample)

    world_design = creative_package.get("worldDesign", {})
    if isinstance(world_design, dict) and world_design:
        write_json(bundle.creative_dir / "01_world_design.json", world_design)

    _write_markdown_if_present(bundle.creative_dir / "02_environment_design.md", str(creative_package.get("environmentDesign", "")))
    _write_markdown_if_present(bundle.creative_dir / "03_styling_design.md", str(creative_package.get("stylingDesign", "")))
    _write_markdown_if_present(bundle.creative_dir / "04_action_design.md", str(creative_package.get("actionDesign", "")))
    write_json(bundle.creative_dir / "05_creative_package.json", creative_package)


def materialize_prompt_package(bundle, prompt_package: dict[str, Any]) -> dict[str, Any]:
    normalized_positive = _normalize_text(prompt_package.get("positivePrompt", prompt_package.get("positive", "")))
    normalized_negative = _normalize_text(prompt_package.get("negativePrompt", prompt_package.get("negative", "")))
    if not normalized_positive or not normalized_negative:
        raise RuntimeError("Prompt package must contain positivePrompt and negativePrompt.")

    normalized_package = {
        "meta": dict(prompt_package.get("meta", {}) or {}),
        "defaultRunContext": dict(prompt_package.get("defaultRunContext", {}) or {}),
        "positivePrompt": normalized_positive,
        "negativePrompt": normalized_negative,
        "reviewStatus": _normalize_text(prompt_package.get("reviewStatus")) or "external",
        "promptChanged": bool(prompt_package.get("promptChanged", False)),
        "reviewIssues": [
            _normalize_text(item)
            for item in (prompt_package.get("reviewIssues", []) or [])
            if _normalize_text(item)
        ],
        "changeSummary": _normalize_text(prompt_package.get("changeSummary")) or "External prompt package import.",
    }
    write_json(bundle.prompt_guard_dir / "02_prompt_package.json", normalized_package)
    return normalized_package


def _build_execution_prompt_package(
    request: dict[str, Any],
    prompt_package: dict[str, Any],
) -> dict[str, Any]:
    normalized_package = {
        **dict(prompt_package or {}),
        "meta": dict(prompt_package.get("meta", {}) or {}),
        "defaultRunContext": dict(prompt_package.get("defaultRunContext", {}) or {}),
        "reviewIssues": list(prompt_package.get("reviewIssues", []) or []),
    }
    request_id = _normalize_text(request.get("requestId"))
    if request_id:
        normalized_package["seedSalt"] = request_id
    return normalized_package


def _build_generation_context(project_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    character_assets = load_character_assets(project_dir)
    default_run_context = build_default_run_context(
        now_local=datetime.now().isoformat(timespec="seconds"),
    )
    return character_assets, default_run_context


def _normalize_signal_lines(raw_text: str) -> list[str]:
    normalized_lines: list[str] = []
    for raw_line in str(raw_text or "").splitlines():
        line = normalize_spaces(raw_line).lstrip("-•*").strip()
        if line:
            normalized_lines.append(line)
    return normalized_lines


def _parse_social_signal_sample_inline(raw_text: str) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        raise RuntimeError("Sample content cannot be empty.")
    try:
        raw_payload = json.loads(text)
    except Exception:
        raw_payload = None
    if isinstance(raw_payload, dict):
        payload = raw_payload.get("socialSignalSample") if isinstance(raw_payload.get("socialSignalSample"), dict) else raw_payload
        sampled_signals = payload.get("sampledSignalsZh") if isinstance(payload, dict) else None
        if isinstance(sampled_signals, list):
            normalized_signals = [normalize_spaces(str(item)) for item in sampled_signals if normalize_spaces(str(item))]
            if normalized_signals:
                return {"sampledSignalsZh": normalized_signals}
    if isinstance(raw_payload, list):
        normalized_signals = [normalize_spaces(str(item)) for item in raw_payload if normalize_spaces(str(item))]
        if normalized_signals:
            return {"sampledSignalsZh": normalized_signals}
    normalized_lines = _normalize_signal_lines(text)
    if not normalized_lines:
        raise RuntimeError("Sample content did not produce any usable signals.")
    return {"sampledSignalsZh": normalized_lines}


def _build_inline_creative_package(request: dict[str, Any], default_run_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "meta": {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "runMode": default_run_context.get("runMode", "content_workbench"),
            "source": "content_workbench_inline",
        },
        "defaultRunContext": default_run_context,
        "worldDesign": {
            "scenePremiseZh": str(request.get("scenePremiseText", "")).strip(),
            "worldSceneZh": str(request.get("worldSceneText", "")).strip(),
        },
        "environmentDesign": str(request.get("environmentDesignText", "")).strip(),
        "stylingDesign": str(request.get("stylingDesignText", "")).strip(),
        "actionDesign": str(request.get("actionDesignText", "")).strip(),
    }


def _build_inline_prompt_package(request: dict[str, Any], default_run_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "meta": {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "runMode": default_run_context.get("runMode", "content_workbench"),
            "source": "content_workbench_inline",
        },
        "defaultRunContext": default_run_context,
        "positivePrompt": str(request.get("positivePromptText", "")).strip(),
        "negativePrompt": str(request.get("negativePromptText", "")).strip(),
        "reviewStatus": "external",
        "promptChanged": False,
        "reviewIssues": [],
        "changeSummary": "Inline prompt package created by content workbench.",
    }


def _write_input_snapshots(bundle, *, default_run_context: dict[str, Any], character_assets: dict[str, Any]) -> None:
    write_json(bundle.input_dir / "default_run_context.json", default_run_context)
    write_json(bundle.input_dir / "character_assets_snapshot.json", character_assets)


def _write_workbench_request(bundle, request: dict[str, Any], source_meta: dict[str, Any]) -> None:
    write_json(bundle.input_dir / "content_workbench_request.json", request)
    write_json(bundle.input_dir / "content_workbench_source.json", source_meta)


def _write_summary(
    bundle,
    *,
    request: dict[str, Any],
    source_meta: dict[str, Any],
    creative_package: dict[str, Any] | None = None,
    social_post_package: dict[str, Any] | None = None,
    prompt_builder_package: dict[str, Any] | None = None,
    prompt_package: dict[str, Any] | None = None,
    execution_package: dict[str, Any] | None = None,
) -> dict[str, Any]:
    creative_payload = creative_package or {}
    social_payload = social_post_package or {}
    prompt_builder_payload = prompt_builder_package or {}
    prompt_payload = prompt_package or {}
    execution_payload = execution_package or {}
    summary = {
        "runId": bundle.run_id,
        "sourceKind": request["sourceKind"],
        "sourceKindLabel": SOURCE_KIND_LABELS[request["sourceKind"]],
        "endStage": request["endStage"],
        "endStageLabel": END_STAGE_LABELS[request["endStage"]],
        "label": request["label"],
        "sourceMeta": source_meta,
        "creativePackagePath": str(bundle.creative_dir / "05_creative_package.json") if (bundle.creative_dir / "05_creative_package.json").exists() else "",
        "socialPostPackagePath": str(bundle.social_post_dir / "01_social_post_package.json") if (bundle.social_post_dir / "01_social_post_package.json").exists() else "",
        "promptBuilderPackagePath": str(bundle.prompt_builder_dir / "01_prompt_package.json") if (bundle.prompt_builder_dir / "01_prompt_package.json").exists() else "",
        "promptPackagePath": str(bundle.prompt_guard_dir / "02_prompt_package.json") if (bundle.prompt_guard_dir / "02_prompt_package.json").exists() else "",
        "promptGuardReportPath": str(bundle.prompt_guard_dir / "01_review_report.json") if (bundle.prompt_guard_dir / "01_review_report.json").exists() else "",
        "executionPackagePath": str(bundle.execution_dir / "04_execution_package.json") if (bundle.execution_dir / "04_execution_package.json").exists() else "",
        "sceneDraftPremiseZh": str(creative_payload.get("worldDesign", {}).get("scenePremiseZh", "")).strip(),
        "sceneDraftTextZh": str(creative_payload.get("worldDesign", {}).get("worldSceneZh", "")).strip(),
        "socialPostText": str(social_payload.get("socialPostText", "")).strip(),
        "promptBuilderPositivePromptText": str(prompt_builder_payload.get("positivePrompt", "")).strip(),
        "promptBuilderNegativePromptText": str(prompt_builder_payload.get("negativePrompt", "")).strip(),
        "positivePromptText": str(prompt_payload.get("positivePrompt", "")).strip(),
        "negativePromptText": str(prompt_payload.get("negativePrompt", "")).strip(),
        "promptReviewStatus": str(prompt_payload.get("reviewStatus", "")).strip(),
        "promptChanged": bool(prompt_payload.get("promptChanged", False)),
        "promptReviewIssues": [
            str(item).strip()
            for item in (prompt_payload.get("reviewIssues", []) or [])
            if str(item).strip()
        ],
        "promptChangeSummary": str(prompt_payload.get("changeSummary", "")).strip(),
        "promptSeedSalt": str(prompt_payload.get("seedSalt", "")).strip(),
        "generatedImagePath": str(execution_payload.get("imagePath", "")).strip(),
    }
    write_json(bundle.output_dir / "run_summary.json", summary)
    return summary


def _run_prompt_pipeline(
    project_dir: Path,
    bundle,
    *,
    default_run_context: dict[str, Any],
    character_assets: dict[str, Any],
    creative_package: dict[str, Any],
    log: Callable[[str], None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if log is not None:
        log("prompt builder layer: three design drafts -> image prompt")
    prompt_builder_package = run_prompt_builder_pipeline(
        project_dir,
        bundle,
        default_run_context,
        character_assets,
        creative_package,
        resolve_creative_model_config_path(project_dir),
    )
    if log is not None:
        log("prompt guard layer: final prompt review -> minimal patch")
    prompt_package = run_prompt_guard_pipeline(
        project_dir,
        bundle,
        default_run_context,
        character_assets,
        creative_package,
        prompt_builder_package,
        resolve_prompt_guard_model_config_path(project_dir),
    )
    return prompt_builder_package, prompt_package


def _run_from_scene_draft(
    project_dir: Path,
    bundle,
    *,
    request: dict[str, Any],
    source_meta: dict[str, Any],
    scene_draft: dict[str, Any],
    creative_extras: dict[str, Any] | None = None,
    log: Callable[[str], None] | None = None,
    should_abort: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    character_assets, default_run_context = _build_generation_context(project_dir)
    default_run_context = dict(default_run_context)
    default_run_context["runMode"] = "content_workbench"
    _write_input_snapshots(bundle, default_run_context=default_run_context, character_assets=character_assets)
    _write_workbench_request(bundle, request, source_meta)
    write_json(bundle.creative_dir / "01_world_design.json", scene_draft)

    creative_package: dict[str, Any] = {
        "meta": {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "runMode": default_run_context["runMode"],
        },
        "defaultRunContext": default_run_context,
        "worldDesign": scene_draft,
        **(creative_extras or {}),
    }
    social_post_package: dict[str, Any] | None = None
    prompt_builder_package: dict[str, Any] | None = None
    prompt_package: dict[str, Any] | None = None
    execution_package: dict[str, Any] | None = None

    if request["endStage"] == END_STAGE_SCENE_DRAFT:
        write_json(bundle.creative_dir / "05_creative_package.json", creative_package)
        summary = _write_summary(bundle, request=request, source_meta=source_meta, creative_package=creative_package)
        return {"summary": summary, "runId": bundle.run_id}

    _maybe_abort(should_abort)
    if log is not None:
        log("creative layer: scene draft -> environment, styling, action designs")
    design_branches = run_parallel_design_stages(
        project_dir,
        bundle,
        character_assets["subjectProfile"],
        scene_draft,
        resolve_creative_model_config_path(project_dir),
    )
    creative_package.update(design_branches)
    materialize_creative_snapshot(bundle, creative_package)

    if request["endStage"] == END_STAGE_DESIGN:
        summary = _write_summary(bundle, request=request, source_meta=source_meta, creative_package=creative_package)
        return {"summary": summary, "runId": bundle.run_id}

    _maybe_abort(should_abort)
    if log is not None:
        log("social post layer: character assets + scene draft -> social post text")
    social_post_package = run_social_post_pipeline(
        project_dir,
        bundle,
        default_run_context,
        character_assets,
        creative_package,
        resolve_creative_model_config_path(project_dir),
    )

    if request["endStage"] == END_STAGE_SOCIAL_POST:
        summary = _write_summary(
            bundle,
            request=request,
            source_meta=source_meta,
            creative_package=creative_package,
            social_post_package=social_post_package,
        )
        return {"summary": summary, "runId": bundle.run_id}

    _maybe_abort(should_abort)
    prompt_builder_package, prompt_package = _run_prompt_pipeline(
        project_dir,
        bundle,
        default_run_context=default_run_context,
        character_assets=character_assets,
        creative_package=creative_package,
        log=log,
    )

    if request["endStage"] == END_STAGE_PROMPT:
        summary = _write_summary(
            bundle,
            request=request,
            source_meta=source_meta,
            creative_package=creative_package,
            social_post_package=social_post_package,
            prompt_builder_package=prompt_builder_package,
            prompt_package=prompt_package,
        )
        return {"summary": summary, "runId": bundle.run_id}

    _maybe_abort(should_abort)
    if log is not None:
        log("execution layer: final prompt -> ComfyUI workflow -> generated image")
    execution_prompt_package = _build_execution_prompt_package(request, prompt_package)
    execution_package = run_execution_pipeline(
        project_dir,
        bundle,
        default_run_context,
        execution_prompt_package,
        should_abort=should_abort,
    )
    summary = _write_summary(
        bundle,
        request=request,
        source_meta=source_meta,
        creative_package=creative_package,
        social_post_package=social_post_package,
        prompt_builder_package=prompt_builder_package,
        prompt_package=execution_prompt_package,
        execution_package=execution_package,
    )
    return {"summary": summary, "runId": bundle.run_id}


def _run_from_sample_file(
    project_dir: Path,
    bundle,
    *,
    request: dict[str, Any],
    log: Callable[[str], None] | None = None,
    should_abort: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    source_path = Path(request["sourcePath"]).resolve()
    source_payload = read_json(source_path)
    social_signal_sample = source_payload.get("socialSignalSample", {})
    if not isinstance(social_signal_sample, dict) or not social_signal_sample.get("sampledSignalsZh"):
        raise RuntimeError(f"Missing socialSignalSample in {source_path}")

    character_assets, default_run_context = _build_generation_context(project_dir)
    default_run_context = dict(default_run_context)
    default_run_context["runMode"] = "content_workbench"
    _write_input_snapshots(bundle, default_run_context=default_run_context, character_assets=character_assets)
    _write_workbench_request(
        bundle,
        request,
        {
            "sourcePath": str(source_path),
            "sourceKind": request["sourceKind"],
        },
    )
    write_json(bundle.creative_dir / "01_world_design_input.json", {"socialSignalSample": social_signal_sample})
    write_json(bundle.input_dir / "social_signal_sample_snapshot.json", social_signal_sample)

    _maybe_abort(should_abort)
    if log is not None:
        log("creative layer: sampled signals -> world design")
    world_design = run_world_design_stage(
        project_dir,
        bundle,
        character_assets["subjectProfile"],
        social_signal_sample,
        resolve_creative_model_config_path(project_dir),
    )

    return _run_from_scene_draft(
        project_dir,
        bundle,
        request=request,
        source_meta={
            "sourcePath": str(source_path),
            "sourceKind": request["sourceKind"],
        },
        scene_draft=world_design,
        creative_extras={"socialSignalSample": social_signal_sample},
        log=log,
        should_abort=should_abort,
    )


def _run_from_sample_text(
    project_dir: Path,
    bundle,
    *,
    request: dict[str, Any],
    log: Callable[[str], None] | None = None,
    should_abort: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    social_signal_sample = _parse_social_signal_sample_inline(request["sourceContent"])
    character_assets, default_run_context = _build_generation_context(project_dir)
    default_run_context = dict(default_run_context)
    default_run_context["runMode"] = "content_workbench"
    _write_input_snapshots(bundle, default_run_context=default_run_context, character_assets=character_assets)
    _write_workbench_request(
        bundle,
        request,
        {
            "sourceKind": request["sourceKind"],
            "inline": True,
        },
    )
    write_json(bundle.creative_dir / "01_world_design_input.json", {"socialSignalSample": social_signal_sample})
    write_json(bundle.input_dir / "social_signal_sample_snapshot.json", social_signal_sample)

    _maybe_abort(should_abort)
    if log is not None:
        log("creative layer: inline sampled signals -> world design")
    world_design = run_world_design_stage(
        project_dir,
        bundle,
        character_assets["subjectProfile"],
        social_signal_sample,
        resolve_creative_model_config_path(project_dir),
    )
    return _run_from_scene_draft(
        project_dir,
        bundle,
        request=request,
        source_meta={
            "sourceKind": request["sourceKind"],
            "inline": True,
        },
        scene_draft=world_design,
        creative_extras={"socialSignalSample": social_signal_sample},
        log=log,
        should_abort=should_abort,
    )


def _run_from_live_sampling(
    project_dir: Path,
    bundle,
    *,
    request: dict[str, Any],
    log: Callable[[str], None] | None = None,
    should_abort: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    character_assets, default_run_context = _build_generation_context(project_dir)
    write_json(bundle.input_dir / "default_run_context.json", default_run_context)
    write_json(bundle.input_dir / "character_assets_snapshot.json", character_assets)
    _write_workbench_request(bundle, request, {"sourceKind": request["sourceKind"], "inline": True})

    _maybe_abort(should_abort)
    if log is not None:
        log("creative layer: character assets + live social sampling -> scene draft -> three design drafts")
    creative_package = run_creative_pipeline(
        project_dir,
        bundle,
        default_run_context,
        character_assets,
        resolve_creative_model_config_path(project_dir),
    )

    _maybe_abort(should_abort)
    if log is not None:
        log("social post layer: character assets + scene draft -> social post text")
    social_post_package = run_social_post_pipeline(
        project_dir,
        bundle,
        default_run_context,
        character_assets,
        creative_package,
        resolve_creative_model_config_path(project_dir),
    )

    _maybe_abort(should_abort)
    prompt_builder_package, prompt_package = _run_prompt_pipeline(
        project_dir,
        bundle,
        default_run_context=default_run_context,
        character_assets=character_assets,
        creative_package=creative_package,
        log=log,
    )

    _maybe_abort(should_abort)
    if log is not None:
        log("execution layer: image prompt -> ComfyUI workflow -> generated image")
    execution_prompt_package = _build_execution_prompt_package(request, prompt_package)
    execution_package = run_execution_pipeline(
        project_dir,
        bundle,
        default_run_context,
        execution_prompt_package,
        should_abort=should_abort,
    )

    summary = _write_summary(
        bundle,
        request=request,
        source_meta={"sourceKind": request["sourceKind"], "inline": True},
        creative_package=creative_package,
        social_post_package=social_post_package,
        prompt_builder_package=prompt_builder_package,
        prompt_package=execution_prompt_package,
        execution_package=execution_package,
    )
    return {"summary": summary, "runId": bundle.run_id}


def _run_from_creative_package_file(
    project_dir: Path,
    bundle,
    *,
    request: dict[str, Any],
    log: Callable[[str], None] | None = None,
    should_abort: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    source_path = Path(request["sourcePath"]).resolve()
    creative_package = read_json(source_path)
    character_assets = load_character_assets(project_dir)
    default_run_context = creative_package.get("defaultRunContext") or build_default_run_context(
        now_local=datetime.now().isoformat(timespec="seconds"),
    )
    default_run_context = dict(default_run_context)
    default_run_context["runMode"] = "content_workbench"
    _write_input_snapshots(bundle, default_run_context=default_run_context, character_assets=character_assets)
    _write_workbench_request(
        bundle,
        request,
        {
            "sourcePath": str(source_path),
            "sourceKind": request["sourceKind"],
        },
    )
    materialize_creative_snapshot(bundle, creative_package)

    social_post_package: dict[str, Any] | None = None
    prompt_builder_package: dict[str, Any] | None = None
    prompt_package: dict[str, Any] | None = None
    execution_package: dict[str, Any] | None = None

    _maybe_abort(should_abort)
    if log is not None:
        log("social post layer: creative package -> social post text")
    social_post_package = run_social_post_pipeline(
        project_dir,
        bundle,
        default_run_context,
        character_assets,
        creative_package,
        resolve_creative_model_config_path(project_dir),
    )

    if request["endStage"] == END_STAGE_SOCIAL_POST:
        summary = _write_summary(
            bundle,
            request=request,
            source_meta={"sourcePath": str(source_path), "sourceKind": request["sourceKind"]},
            creative_package=creative_package,
            social_post_package=social_post_package,
        )
        return {"summary": summary, "runId": bundle.run_id}

    _maybe_abort(should_abort)
    prompt_builder_package, prompt_package = _run_prompt_pipeline(
        project_dir,
        bundle,
        default_run_context=default_run_context,
        character_assets=character_assets,
        creative_package=creative_package,
        log=log,
    )
    if request["endStage"] == END_STAGE_PROMPT:
        summary = _write_summary(
            bundle,
            request=request,
            source_meta={"sourcePath": str(source_path), "sourceKind": request["sourceKind"]},
            creative_package=creative_package,
            social_post_package=social_post_package,
            prompt_builder_package=prompt_builder_package,
            prompt_package=prompt_package,
        )
        return {"summary": summary, "runId": bundle.run_id}

    _maybe_abort(should_abort)
    if log is not None:
        log("execution layer: final prompt -> ComfyUI workflow -> generated image")
    execution_prompt_package = _build_execution_prompt_package(request, prompt_package)
    execution_package = run_execution_pipeline(
        project_dir,
        bundle,
        default_run_context,
        execution_prompt_package,
        should_abort=should_abort,
    )
    summary = _write_summary(
        bundle,
        request=request,
        source_meta={"sourcePath": str(source_path), "sourceKind": request["sourceKind"]},
        creative_package=creative_package,
        social_post_package=social_post_package,
        prompt_builder_package=prompt_builder_package,
        prompt_package=execution_prompt_package,
        execution_package=execution_package,
    )
    return {"summary": summary, "runId": bundle.run_id}


def _run_from_prompt_package_file(
    project_dir: Path,
    bundle,
    *,
    request: dict[str, Any],
    log: Callable[[str], None] | None = None,
    should_abort: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    source_path = Path(request["sourcePath"]).resolve()
    source_payload = read_json(source_path)
    default_run_context = source_payload.get("defaultRunContext") or build_default_run_context(
        now_local=datetime.now().isoformat(timespec="seconds"),
    )
    default_run_context = dict(default_run_context)
    default_run_context["runMode"] = "content_workbench"
    character_assets = load_character_assets(project_dir)
    _write_input_snapshots(bundle, default_run_context=default_run_context, character_assets=character_assets)
    _write_workbench_request(
        bundle,
        request,
        {
            "sourcePath": str(source_path),
            "sourceKind": request["sourceKind"],
        },
    )
    prompt_package = materialize_prompt_package(bundle, source_payload)

    _maybe_abort(should_abort)
    if log is not None:
        log("execution layer: imported prompt package -> ComfyUI workflow -> generated image")
    execution_prompt_package = _build_execution_prompt_package(request, prompt_package)
    execution_package = run_execution_pipeline(
        project_dir,
        bundle,
        default_run_context,
        execution_prompt_package,
        should_abort=should_abort,
    )
    summary = _write_summary(
        bundle,
        request=request,
        source_meta={"sourcePath": str(source_path), "sourceKind": request["sourceKind"]},
        prompt_package=execution_prompt_package,
        execution_package=execution_package,
    )
    return {"summary": summary, "runId": bundle.run_id}


def _run_from_creative_package_data(
    project_dir: Path,
    bundle,
    *,
    request: dict[str, Any],
    creative_package: dict[str, Any],
    source_meta: dict[str, Any],
    log: Callable[[str], None] | None = None,
    should_abort: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    character_assets = load_character_assets(project_dir)
    default_run_context = creative_package.get("defaultRunContext") or build_default_run_context(
        now_local=datetime.now().isoformat(timespec="seconds"),
    )
    default_run_context = dict(default_run_context)
    default_run_context["runMode"] = "content_workbench"
    creative_package["defaultRunContext"] = default_run_context
    _write_input_snapshots(bundle, default_run_context=default_run_context, character_assets=character_assets)
    _write_workbench_request(bundle, request, source_meta)
    materialize_creative_snapshot(bundle, creative_package)

    social_post_package: dict[str, Any] | None = None
    prompt_builder_package: dict[str, Any] | None = None
    prompt_package: dict[str, Any] | None = None
    execution_package: dict[str, Any] | None = None

    _maybe_abort(should_abort)
    if log is not None:
        log("social post layer: creative package -> social post text")
    social_post_package = run_social_post_pipeline(
        project_dir,
        bundle,
        default_run_context,
        character_assets,
        creative_package,
        resolve_creative_model_config_path(project_dir),
    )
    if request["endStage"] == END_STAGE_SOCIAL_POST:
        summary = _write_summary(
            bundle,
            request=request,
            source_meta=source_meta,
            creative_package=creative_package,
            social_post_package=social_post_package,
        )
        return {"summary": summary, "runId": bundle.run_id}

    _maybe_abort(should_abort)
    prompt_builder_package, prompt_package = _run_prompt_pipeline(
        project_dir,
        bundle,
        default_run_context=default_run_context,
        character_assets=character_assets,
        creative_package=creative_package,
        log=log,
    )
    if request["endStage"] == END_STAGE_PROMPT:
        summary = _write_summary(
            bundle,
            request=request,
            source_meta=source_meta,
            creative_package=creative_package,
            social_post_package=social_post_package,
            prompt_builder_package=prompt_builder_package,
            prompt_package=prompt_package,
        )
        return {"summary": summary, "runId": bundle.run_id}

    _maybe_abort(should_abort)
    if log is not None:
        log("execution layer: final prompt -> ComfyUI workflow -> generated image")
    execution_prompt_package = _build_execution_prompt_package(request, prompt_package)
    execution_package = run_execution_pipeline(
        project_dir,
        bundle,
        default_run_context,
        execution_prompt_package,
        should_abort=should_abort,
    )
    summary = _write_summary(
        bundle,
        request=request,
        source_meta=source_meta,
        creative_package=creative_package,
        social_post_package=social_post_package,
        prompt_builder_package=prompt_builder_package,
        prompt_package=execution_prompt_package,
        execution_package=execution_package,
    )
    return {"summary": summary, "runId": bundle.run_id}


def _run_from_prompt_package_data(
    project_dir: Path,
    bundle,
    *,
    request: dict[str, Any],
    prompt_package: dict[str, Any],
    source_meta: dict[str, Any],
    log: Callable[[str], None] | None = None,
    should_abort: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    default_run_context = prompt_package.get("defaultRunContext") or build_default_run_context(
        now_local=datetime.now().isoformat(timespec="seconds"),
    )
    default_run_context = dict(default_run_context)
    default_run_context["runMode"] = "content_workbench"
    prompt_package["defaultRunContext"] = default_run_context
    character_assets = load_character_assets(project_dir)
    _write_input_snapshots(bundle, default_run_context=default_run_context, character_assets=character_assets)
    _write_workbench_request(bundle, request, source_meta)
    normalized_prompt_package = materialize_prompt_package(bundle, prompt_package)

    _maybe_abort(should_abort)
    if log is not None:
        log("execution layer: imported prompt package -> ComfyUI workflow -> generated image")
    execution_prompt_package = _build_execution_prompt_package(request, normalized_prompt_package)
    execution_package = run_execution_pipeline(
        project_dir,
        bundle,
        default_run_context,
        execution_prompt_package,
        should_abort=should_abort,
    )
    summary = _write_summary(
        bundle,
        request=request,
        source_meta=source_meta,
        prompt_package=execution_prompt_package,
        execution_package=execution_package,
    )
    return {"summary": summary, "runId": bundle.run_id}


def _execute_normalized_request(
    project_dir: Path,
    bundle,
    normalized_request: dict[str, Any],
    *,
    log: Callable[[str], None] | None = None,
    should_abort: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    owner_label = normalize_spaces(normalized_request.get("label")) or SOURCE_KIND_LABELS.get(
        normalized_request["sourceKind"],
        "内容测试工作台",
    )
    with occupy_generation_slot(
        project_dir,
        owner_type="content_workbench",
        owner_label=owner_label,
        run_id=bundle.run_id,
        metadata={
            "sourceKind": normalized_request["sourceKind"],
            "endStage": normalized_request["endStage"],
        },
    ):
        if normalized_request["sourceKind"] == SOURCE_KIND_SCENE_DRAFT_TEXT:
            scene_draft = parse_scene_draft_message(normalized_request["sceneDraftText"])
            return _run_from_scene_draft(
                project_dir,
                bundle,
                request=normalized_request,
                source_meta={"sourceKind": normalized_request["sourceKind"], "inline": True},
                scene_draft=scene_draft,
                log=log,
                should_abort=should_abort,
            )
        if normalized_request["sourceKind"] == SOURCE_KIND_SCENE_DRAFT_FILE:
            scene_draft = read_json(Path(normalized_request["sourcePath"]))
            return _run_from_scene_draft(
                project_dir,
                bundle,
                request=normalized_request,
                source_meta={"sourcePath": normalized_request["sourcePath"], "sourceKind": normalized_request["sourceKind"]},
                scene_draft=scene_draft,
                log=log,
                should_abort=should_abort,
            )
        if normalized_request["sourceKind"] == SOURCE_KIND_LIVE_SAMPLING:
            return _run_from_live_sampling(
                project_dir,
                bundle,
                request=normalized_request,
                log=log,
                should_abort=should_abort,
            )
        if normalized_request["sourceKind"] == SOURCE_KIND_SAMPLE_TEXT:
            return _run_from_sample_text(
                project_dir,
                bundle,
                request=normalized_request,
                log=log,
                should_abort=should_abort,
            )
        if normalized_request["sourceKind"] == SOURCE_KIND_SAMPLE_FILE:
            return _run_from_sample_file(
                project_dir,
                bundle,
                request=normalized_request,
                log=log,
                should_abort=should_abort,
            )
        if normalized_request["sourceKind"] == SOURCE_KIND_CREATIVE_PACKAGE_TEXT:
            character_assets, default_run_context = _build_generation_context(project_dir)
            creative_package = _build_inline_creative_package(normalized_request, default_run_context)
            return _run_from_creative_package_data(
                project_dir,
                bundle,
                request=normalized_request,
                creative_package=creative_package,
                source_meta={"sourceKind": normalized_request["sourceKind"], "inline": True},
                log=log,
                should_abort=should_abort,
            )
        if normalized_request["sourceKind"] == SOURCE_KIND_CREATIVE_PACKAGE_FILE:
            return _run_from_creative_package_file(
                project_dir,
                bundle,
                request=normalized_request,
                log=log,
                should_abort=should_abort,
            )
        if normalized_request["sourceKind"] == SOURCE_KIND_PROMPT_PACKAGE_TEXT:
            _character_assets, default_run_context = _build_generation_context(project_dir)
            prompt_package = _build_inline_prompt_package(normalized_request, default_run_context)
            return _run_from_prompt_package_data(
                project_dir,
                bundle,
                request=normalized_request,
                prompt_package=prompt_package,
                source_meta={"sourceKind": normalized_request["sourceKind"], "inline": True},
                log=log,
                should_abort=should_abort,
            )
        if normalized_request["sourceKind"] == SOURCE_KIND_PROMPT_PACKAGE_FILE:
            return _run_from_prompt_package_file(
                project_dir,
                bundle,
                request=normalized_request,
                log=log,
                should_abort=should_abort,
            )
        raise RuntimeError(f"Unsupported sourceKind: {normalized_request['sourceKind']}")


def execute_workbench_task_in_bundle(
    project_dir: Path,
    bundle,
    request: dict[str, Any],
    *,
    log: Callable[[str], None] | None = None,
    should_abort: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    normalized_request = validate_workbench_request(project_dir, request)
    return {
        "bundle": bundle,
        **_execute_normalized_request(
            project_dir,
            bundle,
            normalized_request,
            log=log,
            should_abort=should_abort,
        ),
        "request": normalized_request,
    }


def execute_workbench_task(
    project_dir: Path,
    request: dict[str, Any],
    *,
    log: Callable[[str], None] | None = None,
    should_abort: Callable[[], bool] | None = None,
    on_bundle_created: Callable[[Any, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    normalized_request = validate_workbench_request(project_dir, request)
    bundle = create_run_bundle(project_dir, "content_workbench", normalized_request["label"])
    if on_bundle_created is not None:
        on_bundle_created(bundle, normalized_request)
    return {
        "bundle": bundle,
        **_execute_normalized_request(
            project_dir,
            bundle,
            normalized_request,
            log=log,
            should_abort=should_abort,
        ),
        "request": normalized_request,
    }
