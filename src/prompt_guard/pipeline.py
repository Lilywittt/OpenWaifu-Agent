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

from .contracts import prompt_guard_contract


PROMPT_PATH = "prompts/prompt_guard/review_and_patch_prompt.md"
INPUT_FILENAME = "00_prompt_guard_input.json"
REPORT_FILENAME = "01_review_report.json"
PACKAGE_FILENAME = "02_prompt_package.json"
STAGE_NAME = "08_prompt_guard"
ALLOWED_STATUSES = {"approved", "revised"}


def _system_prompt(project_dir: Path) -> str:
    prompt_text = load_prompt_text(project_dir, PROMPT_PATH)
    output_schema = json.dumps(to_deepseek_payload(prompt_guard_contract()), ensure_ascii=False, indent=2)
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


def build_prompt_guard_input(
    prompt_package: dict[str, Any],
    world_design: dict[str, Any],
    subject_profile: dict[str, Any],
) -> dict[str, Any]:
    return {
        "promptPackage": {
            "positivePrompt": str(prompt_package.get("positivePrompt", "")).strip(),
            "negativePrompt": str(prompt_package.get("negativePrompt", "")).strip(),
        },
        "sceneDraft": copy.deepcopy(world_design),
        "subjectProfile": copy.deepcopy(subject_profile),
    }


def _normalize_guard_output(raw_payload: dict[str, Any], original_prompt_package: dict[str, Any]) -> dict[str, Any]:
    payload = from_deepseek_payload(raw_payload)
    positive = normalize_spaces(str(payload.get("positivePrompt", "")))
    negative = normalize_spaces(str(payload.get("negativePrompt", "")))
    if not positive:
        raise RuntimeError("prompt guard returned empty positive prompt.")
    if not negative:
        raise RuntimeError("prompt guard returned empty negative prompt.")

    original_positive = normalize_spaces(str(original_prompt_package.get("positivePrompt", "")))
    original_negative = normalize_spaces(str(original_prompt_package.get("negativePrompt", "")))
    changed = positive != original_positive or negative != original_negative
    status = normalize_spaces(str(payload.get("status", ""))).casefold()
    if status not in ALLOWED_STATUSES:
        status = "revised" if changed else "approved"

    issues_raw = payload.get("issues", [])
    issues = []
    if isinstance(issues_raw, list):
        issues = [normalize_spaces(str(item)) for item in issues_raw if normalize_spaces(str(item))]
    change_summary = normalize_spaces(str(payload.get("changeSummary", "")))
    if not change_summary:
        change_summary = "未修改 prompt。" if not changed else "已根据回调审查结果修改 prompt。"

    return {
        "status": status,
        "changed": changed,
        "issues": issues,
        "changeSummary": change_summary,
        "positivePrompt": positive,
        "negativePrompt": negative,
    }


def run_prompt_guard_pipeline(
    project_dir: Path,
    bundle,
    default_run_context: dict[str, Any],
    character_assets: dict[str, Any],
    creative_package: dict[str, Any],
    prompt_package: dict[str, Any],
    model_config_path: Path,
) -> dict[str, Any]:
    prompt_guard_input = build_prompt_guard_input(
        prompt_package,
        creative_package.get("worldDesign", {}),
        character_assets["subjectProfile"],
    )
    write_json(bundle.prompt_guard_dir / INPUT_FILENAME, prompt_guard_input)
    result = call_json_task(
        project_dir=project_dir,
        model_config_path=model_config_path,
        system_prompt=_system_prompt(project_dir),
        user_payload=to_deepseek_payload({"promptGuardInput": prompt_guard_input}),
        trace_request_path=bundle.trace_dir / "llm" / f"{STAGE_NAME}.request.json",
        trace_response_path=bundle.trace_dir / "llm" / f"{STAGE_NAME}.response.json",
        temperature=0.35,
    )
    review_report = _normalize_guard_output(result, prompt_package)
    write_json(bundle.prompt_guard_dir / REPORT_FILENAME, review_report)

    guarded_prompt_package = {
        "meta": {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "runMode": default_run_context.get("runMode", "default"),
        },
        "defaultRunContext": default_run_context,
        "positivePrompt": review_report["positivePrompt"],
        "negativePrompt": review_report["negativePrompt"],
        "reviewStatus": review_report["status"],
        "promptChanged": review_report["changed"],
        "reviewIssues": review_report["issues"],
        "changeSummary": review_report["changeSummary"],
        "sourcePromptPackagePath": str(bundle.prompt_builder_dir / "01_prompt_package.json"),
    }
    write_json(bundle.prompt_guard_dir / PACKAGE_FILENAME, guarded_prompt_package)
    return guarded_prompt_package
