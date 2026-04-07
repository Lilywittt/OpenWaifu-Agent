from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import normalize_spaces, write_json
from llm import call_json_task
from llm_schema import from_deepseek_payload, to_deepseek_payload
from prompt_loader import load_prompt_text

from .contracts import image_prompt_contract


PROMPT_PATH = "prompts/prompt_builder/image_prompt.md"
INPUT_FILENAME = "00_image_prompt_input.json"
OUTPUT_FILENAME = "00_image_prompt.json"
PACKAGE_FILENAME = "01_prompt_package.json"
STAGE_NAME = "07_image_prompt"


def _system_prompt(project_dir: Path) -> str:
    prompt_text = load_prompt_text(project_dir, PROMPT_PATH)
    output_schema = json.dumps(to_deepseek_payload(image_prompt_contract()), ensure_ascii=False, indent=2)
    return "\n\n".join(
        [
            "<任务区>",
            prompt_text,
            "</任务区>",
            "<返回格式>",
            "请只返回符合下列骨架的合法JSON。",
            output_schema,
            "</返回格式>",
        ]
    )


def _normalize_prompt_output(raw_payload: dict[str, Any]) -> dict[str, str]:
    payload = from_deepseek_payload(raw_payload)
    positive = normalize_spaces(str(payload.get("positive", "")))
    negative = normalize_spaces(str(payload.get("negative", "")))
    if not positive:
        raise RuntimeError("image prompt stage returned empty positive prompt.")
    if not negative:
        raise RuntimeError("image prompt stage returned empty negative prompt.")
    return {
        "positive": positive,
        "negative": negative,
    }


def build_image_prompt_input(subject_profile: dict[str, Any], creative_package: dict[str, Any]) -> dict[str, Any]:
    return {
        "subjectProfile": copy.deepcopy(subject_profile),
        "actionDesign": str(creative_package.get("actionDesign", "")).strip(),
        "stylingDesign": str(creative_package.get("stylingDesign", "")).strip(),
        "environmentDesign": str(creative_package.get("environmentDesign", "")).strip(),
    }


def run_image_prompt_stage(
    project_dir: Path,
    bundle,
    subject_profile: dict[str, Any],
    creative_package: dict[str, Any],
    model_config_path: Path,
) -> dict[str, str]:
    image_prompt_input = build_image_prompt_input(subject_profile, creative_package)
    write_json(bundle.prompt_builder_dir / INPUT_FILENAME, image_prompt_input)
    result = call_json_task(
        project_dir=project_dir,
        model_config_path=model_config_path,
        system_prompt=_system_prompt(project_dir),
        user_payload=to_deepseek_payload({"imagePromptInput": image_prompt_input}),
        trace_request_path=bundle.trace_dir / "llm" / f"{STAGE_NAME}.request.json",
        trace_response_path=bundle.trace_dir / "llm" / f"{STAGE_NAME}.response.json",
        temperature=0.7,
    )
    normalized_result = _normalize_prompt_output(result)
    write_json(bundle.prompt_builder_dir / OUTPUT_FILENAME, normalized_result)
    return normalized_result


def run_prompt_builder_pipeline(
    project_dir: Path,
    bundle,
    default_run_context: dict[str, Any],
    character_assets: dict[str, Any],
    creative_package: dict[str, Any],
    model_config_path: Path,
) -> dict[str, Any]:
    image_prompt = run_image_prompt_stage(
        project_dir,
        bundle,
        character_assets["subjectProfile"],
        creative_package,
        model_config_path,
    )
    prompt_package = {
        "meta": {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "runMode": default_run_context.get("runMode", "default"),
        },
        "defaultRunContext": default_run_context,
        "positivePrompt": image_prompt["positive"],
        "negativePrompt": image_prompt["negative"],
    }
    write_json(bundle.prompt_builder_dir / PACKAGE_FILENAME, prompt_package)
    return prompt_package
