from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import normalize_spaces, write_json, write_text
from llm import call_json_task, call_text_task
from llm_schema import from_deepseek_payload, to_deepseek_payload
from prompt_loader import load_prompt_text

from .contracts import scene_draft_contract, social_signal_filter_contract
from .social_trends import collect_social_trend_sample


STAGE_CONFIGS = {
    "social_signal_filter": {
        "prompt_path": "prompts/creative/social_signal_filter.md",
        "temperature": 0.2,
    },
    "world_design": {
        "prompt_path": "prompts/creative/world_design.md",
        "temperature": 1.3,
    },
    "environment_design": {
        "prompt_path": "prompts/creative/environment_design.md",
        "temperature": 0.7,
    },
    "styling_design": {
        "prompt_path": "prompts/creative/styling_design.md",
        "temperature": 0.7,
    },
    "action_design": {
        "prompt_path": "prompts/creative/action_design.md",
        "temperature": 0.7,
    },
}


class CreativeSocialSamplingError(RuntimeError):
    def __init__(self, detail: str):
        normalized_detail = normalize_spaces(detail)
        self.user_summary = "实时社媒采样失败，当前没有拿到新的外部样本。"
        self.user_details = [
            "失败位置：社媒采样，不是生图执行。",
            "建议：检查网络、代理或 VPN 后重试。",
        ]
        if normalized_detail:
            self.user_details.append(f"技术摘要：{normalized_detail[:160]}")
        super().__init__(
            "实时社媒采样失败：当前没有拿到新的外部样本；"
            "失败位置：社媒采样，不是生图执行；"
            "建议：检查网络、代理或 VPN 后重试。"
            + (f" 技术摘要：{normalized_detail[:200]}" if normalized_detail else "")
        )


def build_default_run_context(*, now_local: str) -> dict[str, Any]:
    return {
        "runMode": "default",
        "nowLocal": now_local,
    }


def _json_system_prompt(project_dir: Path, prompt_path: str, output_contract: dict[str, Any]) -> str:
    prompt_text = load_prompt_text(project_dir, prompt_path)
    output_schema = json.dumps(to_deepseek_payload(output_contract), ensure_ascii=False, indent=2)
    return "\n\n".join(
        [
            "<任务区>",
            prompt_text,
            "</任务区>",
            "<返回格式>",
            "请只返回符合下列骨架的合法 JSON。",
            output_schema,
            "</返回格式>",
        ]
    )


def _text_system_prompt(project_dir: Path, prompt_path: str) -> str:
    prompt_text = load_prompt_text(project_dir, prompt_path)
    return "\n\n".join(
        [
            "<任务区>",
            prompt_text,
            "</任务区>",
            "<输出要求>",
            "直接输出最终设计稿正文。",
            "不要输出 JSON。",
            "不要解释规则或补充题外话。",
            "</输出要求>",
        ]
    )


def _run_json_stage(
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
        system_prompt=_json_system_prompt(project_dir, stage_config["prompt_path"], output_contract),
        user_payload=to_deepseek_payload(user_payload),
        trace_request_path=trace_dir / f"{stage_name}.request.json",
        trace_response_path=trace_dir / f"{stage_name}.response.json",
        temperature=stage_config.get("temperature"),
    )
    normalized_result = from_deepseek_payload(result)
    write_json(bundle.creative_dir / f"{stage_name}.json", normalized_result)
    return normalized_result


def _normalize_text_output(raw_text: str, *, stage_name: str) -> str:
    text = str(raw_text or "").replace("\r\n", "\n").strip()
    if not text:
        raise RuntimeError(f"{stage_name} returned empty text.")
    return text


def _run_text_stage(
    *,
    project_dir: Path,
    model_config_path: Path,
    bundle,
    stage_name: str,
    stage_key: str,
    output_filename: str,
    user_payload: dict[str, Any],
) -> str:
    trace_dir = bundle.trace_dir / "llm"
    stage_config = STAGE_CONFIGS[stage_key]
    result = call_text_task(
        project_dir=project_dir,
        model_config_path=model_config_path,
        system_prompt=_text_system_prompt(project_dir, stage_config["prompt_path"]),
        user_payload=to_deepseek_payload(user_payload),
        trace_request_path=trace_dir / f"{stage_name}.request.json",
        trace_response_path=trace_dir / f"{stage_name}.response.json",
        temperature=stage_config.get("temperature"),
    )
    normalized_result = _normalize_text_output(result, stage_name=stage_name)
    write_text(bundle.creative_dir / output_filename, normalized_result + "\n")
    return normalized_result


def _normalize_summary(payload: dict[str, Any], key: str) -> None:
    payload[key] = normalize_spaces(str(payload.get(key, "")))


def _build_subject_stage_input(subject_profile: dict[str, Any]) -> dict[str, Any]:
    subject_input = copy.deepcopy(subject_profile)
    subject_input.pop("forbidden_changes_zh", None)
    return subject_input


def _build_social_signal_filter_input(social_signal_sample: dict[str, Any]) -> dict[str, Any]:
    signal_candidates = []
    for index, signal in enumerate(social_signal_sample.get("sampledSignalsZh", []), start=1):
        text = normalize_spaces(str(signal))
        if not text:
            continue
        signal_candidates.append(
            {
                "id": f"signal_{index:02d}",
                "textZh": text,
            }
        )
    return {
        "signalCandidates": signal_candidates,
    }


def _normalize_social_signal_filter_result(payload: dict[str, Any]) -> dict[str, Any]:
    payload["selectedSignalId"] = normalize_spaces(str(payload.get("selectedSignalId", "")))
    return payload


def _select_social_signal(social_signal_sample: dict[str, Any], filter_result: dict[str, Any]) -> dict[str, Any]:
    filter_input = _build_social_signal_filter_input(social_signal_sample)
    candidate_lookup = {item["id"]: item["textZh"] for item in filter_input.get("signalCandidates", [])}
    selected_signal_id = normalize_spaces(str(filter_result.get("selectedSignalId", "")))
    if selected_signal_id not in candidate_lookup:
        raise RuntimeError(f"social signal filter returned unknown id: {selected_signal_id or '<empty>'}")
    selected_signal = copy.deepcopy(social_signal_sample)
    selected_signal["sampledSignalsZh"] = [candidate_lookup[selected_signal_id]]
    return selected_signal


def build_world_design_input(subject_profile: dict[str, Any], social_signal_sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "subjectProfile": _build_subject_stage_input(subject_profile),
        "socialSignalSample": copy.deepcopy(social_signal_sample),
    }


def _build_world_derivative_input(subject_profile: dict[str, Any], world_design: dict[str, Any]) -> dict[str, Any]:
    return {
        "subjectProfile": _build_subject_stage_input(subject_profile),
        "sceneDraft": copy.deepcopy(world_design),
    }


def _normalize_world_design(world_design: dict[str, Any]) -> dict[str, Any]:
    for key in ("scenePremiseZh", "worldSceneZh"):
        _normalize_summary(world_design, key)
    return world_design


def run_social_signal_filter_stage(project_dir: Path, bundle, model_config_path: Path) -> dict[str, Any]:
    try:
        social_signal_sample = collect_social_trend_sample(project_dir)
    except Exception as exc:
        raise CreativeSocialSamplingError(str(exc)) from exc
    filter_input = _build_social_signal_filter_input(social_signal_sample)
    if len(filter_input.get("signalCandidates", [])) != 3:
        raise RuntimeError("social signal shortlist must contain exactly 3 candidates")
    write_json(bundle.creative_dir / "00_social_signal_filter_input.json", filter_input)
    filter_result = _normalize_social_signal_filter_result(
        _run_json_stage(
            project_dir=project_dir,
            model_config_path=model_config_path,
            bundle=bundle,
            stage_name="00_social_signal_filter",
            stage_key="social_signal_filter",
            output_contract=social_signal_filter_contract(),
            user_payload={"socialSignalFilterInput": filter_input},
        )
    )
    return _select_social_signal(social_signal_sample, filter_result)


def run_world_design_stage(
    project_dir: Path,
    bundle,
    subject_profile: dict[str, Any],
    social_signal_sample: dict[str, Any],
    model_config_path: Path,
) -> dict[str, Any]:
    world_design_input = build_world_design_input(subject_profile, social_signal_sample)
    write_json(bundle.creative_dir / "01_world_design_input.json", world_design_input)
    world_design = _normalize_world_design(
        _run_json_stage(
            project_dir=project_dir,
            model_config_path=model_config_path,
            bundle=bundle,
            stage_name="01_world_design",
            stage_key="world_design",
            output_contract=scene_draft_contract(),
            user_payload={"worldDesignInput": world_design_input},
        )
    )
    return world_design


def _run_world_derivative_stage(
    *,
    project_dir: Path,
    bundle,
    subject_profile: dict[str, Any],
    world_design: dict[str, Any],
    model_config_path: Path,
    stage_name: str,
    stage_key: str,
    input_filename: str,
    output_filename: str,
    input_key: str,
) -> str:
    stage_input = _build_world_derivative_input(subject_profile, world_design)
    write_json(bundle.creative_dir / input_filename, stage_input)
    return _run_text_stage(
        project_dir=project_dir,
        model_config_path=model_config_path,
        bundle=bundle,
        stage_name=stage_name,
        stage_key=stage_key,
        output_filename=output_filename,
        user_payload={input_key: stage_input},
    )


def run_environment_design_stage(
    project_dir: Path,
    bundle,
    subject_profile: dict[str, Any],
    world_design: dict[str, Any],
    model_config_path: Path,
) -> str:
    return _run_world_derivative_stage(
        project_dir=project_dir,
        bundle=bundle,
        subject_profile=subject_profile,
        world_design=world_design,
        model_config_path=model_config_path,
        stage_name="02_environment_design",
        stage_key="environment_design",
        input_filename="02_environment_design_input.json",
        output_filename="02_environment_design.md",
        input_key="environmentDesignInput",
    )


def run_styling_design_stage(
    project_dir: Path,
    bundle,
    subject_profile: dict[str, Any],
    world_design: dict[str, Any],
    model_config_path: Path,
) -> str:
    return _run_world_derivative_stage(
        project_dir=project_dir,
        bundle=bundle,
        subject_profile=subject_profile,
        world_design=world_design,
        model_config_path=model_config_path,
        stage_name="03_styling_design",
        stage_key="styling_design",
        input_filename="03_styling_design_input.json",
        output_filename="03_styling_design.md",
        input_key="stylingDesignInput",
    )


def run_action_design_stage(
    project_dir: Path,
    bundle,
    subject_profile: dict[str, Any],
    world_design: dict[str, Any],
    model_config_path: Path,
) -> str:
    return _run_world_derivative_stage(
        project_dir=project_dir,
        bundle=bundle,
        subject_profile=subject_profile,
        world_design=world_design,
        model_config_path=model_config_path,
        stage_name="04_action_design",
        stage_key="action_design",
        input_filename="04_action_design_input.json",
        output_filename="04_action_design.md",
        input_key="actionDesignInput",
    )


def run_parallel_design_stages(
    project_dir: Path,
    bundle,
    subject_profile: dict[str, Any],
    world_design: dict[str, Any],
    model_config_path: Path,
) -> dict[str, str]:
    return {
        "environmentDesign": run_environment_design_stage(project_dir, bundle, subject_profile, world_design, model_config_path),
        "stylingDesign": run_styling_design_stage(project_dir, bundle, subject_profile, world_design, model_config_path),
        "actionDesign": run_action_design_stage(project_dir, bundle, subject_profile, world_design, model_config_path),
    }


def run_creative_pipeline(
    project_dir: Path,
    bundle,
    default_run_context: dict[str, Any],
    character_assets: dict,
    model_config_path: Path,
) -> dict[str, Any]:
    subject_profile = character_assets["subjectProfile"]
    social_signal_sample = run_social_signal_filter_stage(project_dir, bundle, model_config_path)
    world_design = run_world_design_stage(project_dir, bundle, subject_profile, social_signal_sample, model_config_path)
    design_branches = run_parallel_design_stages(project_dir, bundle, subject_profile, world_design, model_config_path)

    creative_package = {
        "meta": {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "runMode": "default",
        },
        "defaultRunContext": default_run_context,
        "socialSignalSample": social_signal_sample,
        "worldDesign": world_design,
        **design_branches,
    }
    write_json(bundle.creative_dir / "05_creative_package.json", creative_package)
    return creative_package
