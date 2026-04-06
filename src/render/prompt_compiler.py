from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from io_utils import normalize_spaces, read_json, unique_list, write_json
from llm import call_json_task
from llm_schema import from_deepseek_payload, to_deepseek_payload
from prompt_loader import load_prompt_text


PROMPT_COMPILER_FILE = "prompts/render/prompt_compiler.md"


def _prompt_compiler_contract() -> dict[str, Any]:
    cue_item = {
        "id": "",
        "phraseEn": "",
    }
    return {
        "positiveCuesEn": [cue_item],
        "negativeCuesEn": [cue_item],
        "notesZh": [""],
    }


def _system_prompt(project_dir: Path, output_contract: dict[str, Any]) -> str:
    prompt_text = load_prompt_text(project_dir, PROMPT_COMPILER_FILE)
    output_schema = json.dumps(to_deepseek_payload(output_contract), ensure_ascii=False, indent=2)
    return "\n\n".join(
        [
            "<任务书>",
            prompt_text,
            "</任务书>",
            "<输出要求>",
            "请严格返回合法 JSON。",
            "不要输出解释文字。",
            "不要添加 JSON 骨架里没有的键名。",
            "</输出要求>",
            "<输出骨架>",
            output_schema,
            "</输出骨架>",
        ]
    )


def _normalize_cue_items(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items or []:
        cue_id = normalize_spaces(str(item.get("id", "")))
        phrase = normalize_spaces(str(item.get("phraseEn", "")))
        if not cue_id or cue_id in seen:
            continue
        seen.add(cue_id)
        normalized.append({"id": cue_id, "phraseEn": phrase})
    return normalized


def _cue_lookup(items: list[dict[str, str]]) -> dict[str, str]:
    return {item["id"]: item["phraseEn"] for item in items if item.get("phraseEn")}


def _assemble_positive(render_packet: dict, cue_lookup: dict[str, str]) -> str:
    phrases = [cue_lookup.get(item["id"], item["textZh"]) for item in render_packet.get("positiveFacts", [])]
    phrases.extend(render_packet.get("stylePositiveEn", []))
    return ", ".join(unique_list(phrases))


def _assemble_negative(render_packet: dict, cue_lookup: dict[str, str]) -> str:
    phrases = [cue_lookup.get(item["id"], item["textZh"]) for item in render_packet.get("negativeFacts", [])]
    phrases.extend(render_packet.get("genericNegativeEn", []))
    return ", ".join(unique_list(phrases))


def assemble_prompt_bundle_from_cues(
    render_packet: dict[str, Any],
    positive_cues: list[dict[str, str]],
    negative_cues: list[dict[str, str]],
    notes_zh: list[str] | None = None,
) -> dict[str, Any]:
    positive_lookup = _cue_lookup(_normalize_cue_items(positive_cues))
    negative_lookup = _cue_lookup(_normalize_cue_items(negative_cues))
    return {
        "positivePrompt": _assemble_positive(render_packet, positive_lookup),
        "negativePrompt": _assemble_negative(render_packet, negative_lookup),
        "positiveCuesEn": _normalize_cue_items(positive_cues),
        "negativeCuesEn": _normalize_cue_items(negative_cues),
        "notesZh": unique_list([normalize_spaces(str(item)) for item in (notes_zh or []) if normalize_spaces(str(item))]),
    }


def compile_prompt_bundle(project_dir: Path, bundle, render_packet: dict[str, Any]) -> dict[str, Any]:
    runtime_profile = read_json(project_dir / "config" / "runtime_profile.json")
    model_config_path = project_dir / runtime_profile["creativeModelConfigPath"].replace("./", "")
    compilation = call_json_task(
        project_dir=project_dir,
        model_config_path=model_config_path,
        system_prompt=_system_prompt(project_dir, _prompt_compiler_contract()),
        user_payload=to_deepseek_payload({"renderPacket": render_packet}),
        trace_request_path=bundle.trace_dir / "llm" / "06_prompt_compiler.request.json",
        trace_response_path=bundle.trace_dir / "llm" / "06_prompt_compiler.response.json",
    )
    compilation = from_deepseek_payload(compilation)
    positive_cues = _normalize_cue_items(compilation.get("positiveCuesEn", []))
    negative_cues = _normalize_cue_items(compilation.get("negativeCuesEn", []))
    notes = unique_list([normalize_spaces(str(item)) for item in compilation.get("notesZh", []) if normalize_spaces(str(item))])
    prompt_bundle = assemble_prompt_bundle_from_cues(render_packet, positive_cues, negative_cues, notes)
    write_json(bundle.render_dir / "prompt_bundle.json", prompt_bundle)
    return prompt_bundle
