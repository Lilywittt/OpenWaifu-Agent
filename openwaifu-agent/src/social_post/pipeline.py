from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import write_json, write_text
from llm import call_text_task
from llm_schema import to_deepseek_payload
from model_profiles import resolve_stage_model_profile
from prompt_loader import render_prompt_text


PROMPT_PATH = "prompts/social_post/social_post.md"
INPUT_FILENAME = "00_social_post_input.json"
OUTPUT_FILENAME = "00_social_post.txt"
PACKAGE_FILENAME = "01_social_post_package.json"
FINAL_OUTPUT_FILENAME = "social_post.txt"
STAGE_NAME = "06_social_post"
TEMPERATURE = 1.6


def _render_context_block(value: dict[str, Any]) -> str:
    return json.dumps(to_deepseek_payload(value), ensure_ascii=False, indent=2)


def _system_prompt(project_dir: Path, subject_profile: dict[str, Any], scene_draft: dict[str, Any]) -> str:
    prompt_text = render_prompt_text(
        project_dir,
        PROMPT_PATH,
        {
            "character_asset": _render_context_block(subject_profile),
            "scene_design": _render_context_block(scene_draft),
        },
    )
    return "\n\n".join(
        [
            "<任务区>",
            prompt_text,
            "</任务区>",
            "<输出要求>",
            "直接输出最终社媒文案正文。",
            "不要输出 JSON。",
            "不要解释规则或补充题外话。",
            "</输出要求>",
        ]
    )


def _normalize_social_post_text(raw_text: str) -> str:
    text = str(raw_text or "").replace("\r\n", "\n").strip()
    if not text:
        raise RuntimeError("social post stage returned empty text.")
    return text


def build_social_post_input(subject_profile: dict[str, Any], scene_draft: dict[str, Any]) -> dict[str, Any]:
    return {
        "subjectProfile": copy.deepcopy(subject_profile),
        "sceneDraft": copy.deepcopy(scene_draft),
    }


def run_social_post_stage(
    project_dir: Path,
    bundle,
    subject_profile: dict[str, Any],
    scene_draft: dict[str, Any],
) -> str:
    social_post_input = build_social_post_input(subject_profile, scene_draft)
    write_json(bundle.social_post_dir / INPUT_FILENAME, social_post_input)
    result = call_text_task(
        project_dir=project_dir,
        model_config=resolve_stage_model_profile(project_dir, "social_post.default"),
        system_prompt=_system_prompt(project_dir, social_post_input["subjectProfile"], social_post_input["sceneDraft"]),
        user_payload=None,
        trace_request_path=bundle.trace_dir / "llm" / f"{STAGE_NAME}.request.json",
        trace_response_path=bundle.trace_dir / "llm" / f"{STAGE_NAME}.response.json",
        temperature=TEMPERATURE,
    )
    normalized_result = _normalize_social_post_text(result)
    write_text(bundle.social_post_dir / OUTPUT_FILENAME, normalized_result + "\n")
    return normalized_result


def run_social_post_pipeline(
    project_dir: Path,
    bundle,
    default_run_context: dict[str, Any],
    character_assets: dict[str, Any],
    creative_package: dict[str, Any],
) -> dict[str, Any]:
    scene_draft = copy.deepcopy(creative_package.get("worldDesign", {}))
    social_post_text = run_social_post_stage(
        project_dir,
        bundle,
        character_assets["subjectProfile"],
        scene_draft,
    )
    social_post_package = {
        "meta": {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "runMode": default_run_context.get("runMode", "default"),
        },
        "defaultRunContext": default_run_context,
        "sceneDraftPremiseZh": str(scene_draft.get("scenePremiseZh", "")).strip(),
        "socialPostText": social_post_text,
    }
    write_json(bundle.social_post_dir / PACKAGE_FILENAME, social_post_package)
    write_text(bundle.output_dir / FINAL_OUTPUT_FILENAME, social_post_text + "\n")
    return social_post_package
