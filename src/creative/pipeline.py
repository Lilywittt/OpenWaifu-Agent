from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import normalize_spaces, unique_list, write_json
from llm import call_json_task
from llm_schema import from_deepseek_payload, to_deepseek_payload
from prompt_loader import load_prompt_text
from .contracts import (
    action_design_contract,
    camera_design_contract,
    scene_draft_contract,
    scene_to_design_contract,
    wardrobe_design_contract,
)
from .social_trends import collect_social_trend_sample


STAGE_CONFIGS = {
    "world_design": {
        "prompt_path": "prompts/creative/world_design.md",
        "temperature": 1.3,
    },
    "scene_to_design": {
        "prompt_path": "prompts/creative/scene_to_design.md",
        "temperature": 0.7,
    },
}


def build_default_run_context(*, now_local: str) -> dict[str, Any]:
    return {
        "runMode": "default",
        "nowLocal": now_local,
    }


def _system_prompt(project_dir: Path, prompt_path: str, output_contract: dict[str, Any]) -> str:
    prompt_text = load_prompt_text(project_dir, prompt_path)
    output_schema = json.dumps(to_deepseek_payload(output_contract), ensure_ascii=False, indent=2)
    return "\n\n".join(
        [
            "<任务书>",
            prompt_text,
            "</任务书>",
            "<返回格式>",
            "请只返回符合下列骨架的合法 JSON。",
            output_schema,
            "</返回格式>",
        ]
    )


def _run_stage(
    *,
    project_dir: Path,
    model_config_path: Path,
    bundle,
    stage_name: str,
    stage_key: str,
    output_contract: dict[str, Any],
    user_payload: dict[str, Any],
) -> dict[str, Any]:
    trace_dir = bundle.trace_dir / "llm"
    stage_config = STAGE_CONFIGS[stage_key]
    result = call_json_task(
        project_dir=project_dir,
        model_config_path=model_config_path,
        system_prompt=_system_prompt(project_dir, stage_config["prompt_path"], output_contract),
        user_payload=to_deepseek_payload(user_payload),
        trace_request_path=trace_dir / f"{stage_name}.request.json",
        trace_response_path=trace_dir / f"{stage_name}.response.json",
        temperature=stage_config.get("temperature"),
    )
    normalized_result = from_deepseek_payload(result)
    write_json(bundle.creative_dir / f"{stage_name}.json", normalized_result)
    return normalized_result


def _normalize_text_list(payload: dict[str, Any], key: str) -> None:
    payload[key] = unique_list(
        [normalize_spaces(str(item)) for item in payload.get(key, []) if normalize_spaces(str(item))]
    )


def _normalize_summary(payload: dict[str, Any], key: str) -> None:
    payload[key] = normalize_spaces(str(payload.get(key, "")))


def _normalize_world_design(world_design: dict[str, Any]) -> dict[str, Any]:
    for key in ("scenePremiseZh", "worldSceneZh"):
        _normalize_summary(world_design, key)
    return world_design


def _normalize_action_design(action_design: dict[str, Any]) -> dict[str, Any]:
    for key in ("actionSummaryZh", "momentZh", "bodyActionZh"):
        _normalize_summary(action_design, key)
    for key in ("mustReadZh", "forbiddenDriftZh", "notesZh"):
        _normalize_text_list(action_design, key)
    return action_design


def _normalize_wardrobe_design(wardrobe_design: dict[str, Any]) -> dict[str, Any]:
    _normalize_summary(wardrobe_design, "wardrobeSummaryZh")
    for key in ("requiredZh", "optionalZh", "forbiddenZh", "notesZh"):
        _normalize_text_list(wardrobe_design, key)
    return wardrobe_design


def _normalize_camera_design(camera_design: dict[str, Any]) -> dict[str, Any]:
    for key in ("cameraSummaryZh", "angleZh", "compositionGoalZh"):
        _normalize_summary(camera_design, key)
    for key in ("mustIncludeZh", "forbiddenZh", "notesZh"):
        _normalize_text_list(camera_design, key)
    camera_design["framing"] = normalize_spaces(str(camera_design.get("framing", ""))) or "full_body"
    camera_design["aspectRatio"] = normalize_spaces(str(camera_design.get("aspectRatio", ""))) or "4:5"
    return camera_design


def _build_subject_stage_input(subject_profile: dict[str, Any]) -> dict[str, Any]:
    subject_input = copy.deepcopy(subject_profile)
    subject_input.pop("forbidden_changes_zh", None)
    return subject_input


def build_world_design_input(project_dir: Path, subject_profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "subjectProfile": _build_subject_stage_input(subject_profile),
        "socialSignalSample": collect_social_trend_sample(project_dir),
    }


def _build_scene_to_design_input(subject_profile: dict[str, Any], world_design: dict[str, Any]) -> dict[str, Any]:
    return {
        "subjectProfile": _build_subject_stage_input(subject_profile),
        "sceneDraft": world_design,
    }


def run_world_design_stage(project_dir: Path, bundle, subject_profile: dict[str, Any], model_config_path: Path) -> dict[str, Any]:
    world_design_input = build_world_design_input(project_dir, subject_profile)
    write_json(bundle.creative_dir / "00_world_design_input.json", world_design_input)
    return _normalize_world_design(
        _run_stage(
            project_dir=project_dir,
            model_config_path=model_config_path,
            bundle=bundle,
            stage_name="01_world_design",
            stage_key="world_design",
            output_contract=scene_draft_contract(),
            user_payload={
                "worldDesignInput": world_design_input,
            },
        )
    )


def run_scene_to_design_stage(
    project_dir: Path,
    bundle,
    subject_profile: dict[str, Any],
    world_design: dict[str, Any],
    model_config_path: Path,
) -> dict[str, Any]:
    scene_to_design_input = _build_scene_to_design_input(subject_profile, world_design)
    write_json(bundle.creative_dir / "01_scene_to_design_input.json", scene_to_design_input)
    result = _run_stage(
        project_dir=project_dir,
        model_config_path=model_config_path,
        bundle=bundle,
        stage_name="02_scene_to_design",
        stage_key="scene_to_design",
        output_contract=scene_to_design_contract(),
        user_payload={
            "sceneToDesignInput": scene_to_design_input,
        },
    )
    return {
        "actionDesign": _normalize_action_design(result.get("actionDesign", action_design_contract())),
        "wardrobeDesign": _normalize_wardrobe_design(result.get("wardrobeDesign", wardrobe_design_contract())),
        "cameraDesign": _normalize_camera_design(result.get("cameraDesign", camera_design_contract())),
    }


def run_creative_pipeline(project_dir: Path, bundle, default_run_context: dict[str, Any], character_assets: dict, model_config_path: Path) -> dict[str, Any]:
    subject_profile = character_assets["subjectProfile"]
    world_design = run_world_design_stage(project_dir, bundle, subject_profile, model_config_path)
    scene_to_design = run_scene_to_design_stage(project_dir, bundle, subject_profile, world_design, model_config_path)

    creative_package = {
        "meta": {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "runMode": "default",
        },
        "defaultRunContext": default_run_context,
        "worldDesign": world_design,
        "actionDesign": scene_to_design["actionDesign"],
        "wardrobeDesign": scene_to_design["wardrobeDesign"],
        "cameraDesign": scene_to_design["cameraDesign"],
    }
    write_json(bundle.creative_dir / "creative_package.json", creative_package)
    return creative_package
