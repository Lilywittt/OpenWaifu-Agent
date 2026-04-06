from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import normalize_spaces, unique_list, write_json
from llm import call_json_task
from llm_schema import from_deepseek_payload, to_deepseek_payload
from prompt_loader import load_prompt_text
from .contracts import render_blueprint_contract


PROMPT_FILE = "prompts/render/render_director.md"


def _system_prompt(project_dir: Path, output_contract: dict[str, Any]) -> str:
    prompt_text = load_prompt_text(project_dir, PROMPT_FILE)
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


def _normalize_summary(payload: dict[str, Any], key: str) -> None:
    payload[key] = normalize_spaces(str(payload.get(key, "")))


def _normalize_fact_items(items: list[dict[str, Any]], prefix: str) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    next_index = 1
    for item in items or []:
        raw_id = normalize_spaces(str(item.get("id", ""))).lower().replace(" ", "_").replace("-", "_")
        raw_id = "".join(char for char in raw_id if char.isalnum() or char == "_").strip("_")
        text = normalize_spaces(str(item.get("textZh", "")))
        if not text:
            continue
        if not raw_id:
            raw_id = f"{prefix}_{next_index:02d}"
        while raw_id in seen:
            next_index += 1
            raw_id = f"{prefix}_{next_index:02d}"
        next_index += 1
        seen.add(raw_id)
        normalized.append({"id": raw_id, "textZh": text})
    return normalized


def _normalize_render_blueprint(render_blueprint: dict[str, Any]) -> dict[str, Any]:
    _normalize_summary(render_blueprint, "summaryZh")

    subject = render_blueprint.get("subject", {})
    _normalize_summary(subject, "identityReadZh")
    subject["facts"] = _normalize_fact_items(subject.get("facts", []), "subject")
    subject["forbidden"] = _normalize_fact_items(subject.get("forbidden", []), "subject_forbidden")
    render_blueprint["subject"] = subject

    world = render_blueprint.get("world", {})
    _normalize_summary(world, "summaryZh")
    world["facts"] = _normalize_fact_items(world.get("facts", []), "world")
    world["forbidden"] = _normalize_fact_items(world.get("forbidden", []), "world_forbidden")
    render_blueprint["world"] = world

    action = render_blueprint.get("action", {})
    _normalize_summary(action, "summaryZh")
    action["facts"] = _normalize_fact_items(action.get("facts", []), "action")
    action["forbidden"] = _normalize_fact_items(action.get("forbidden", []), "action_forbidden")
    render_blueprint["action"] = action

    wardrobe = render_blueprint.get("wardrobe", {})
    _normalize_summary(wardrobe, "summaryZh")
    wardrobe["required"] = _normalize_fact_items(wardrobe.get("required", []), "wardrobe")
    wardrobe["optional"] = _normalize_fact_items(wardrobe.get("optional", []), "wardrobe_optional")
    wardrobe["forbidden"] = _normalize_fact_items(wardrobe.get("forbidden", []), "wardrobe_forbidden")
    render_blueprint["wardrobe"] = wardrobe

    camera = render_blueprint.get("camera", {})
    _normalize_summary(camera, "summaryZh")
    camera["framing"] = normalize_spaces(str(camera.get("framing", ""))) or "full_body"
    camera["aspectRatio"] = normalize_spaces(str(camera.get("aspectRatio", ""))) or "4:5"
    camera["facts"] = _normalize_fact_items(camera.get("facts", []), "camera")
    camera["forbidden"] = _normalize_fact_items(camera.get("forbidden", []), "camera_forbidden")
    render_blueprint["camera"] = camera

    positive_ids = {
        item["id"]
        for section in ("subject", "world", "action", "camera")
        for item in render_blueprint.get(section, {}).get("facts", [])
    }
    positive_ids.update(item["id"] for item in render_blueprint.get("wardrobe", {}).get("required", []))
    positive_ids.update(item["id"] for item in render_blueprint.get("wardrobe", {}).get("optional", []))

    negative_ids = {
        item["id"]
        for section in ("subject", "world", "action", "camera")
        for item in render_blueprint.get(section, {}).get("forbidden", [])
    }
    negative_ids.update(item["id"] for item in render_blueprint.get("wardrobe", {}).get("forbidden", []))

    integration = render_blueprint.get("integration", {})
    integration["heroFactIds"] = [item for item in unique_list(integration.get("heroFactIds", [])) if item in positive_ids]
    integration["supportingFactIds"] = [
        item
        for item in unique_list(integration.get("supportingFactIds", []))
        if item in positive_ids and item not in integration["heroFactIds"]
    ]
    integration["negativeFactIds"] = [item for item in unique_list(integration.get("negativeFactIds", [])) if item in negative_ids]
    integration["conflictResolutionsZh"] = unique_list(
        [normalize_spaces(str(item)) for item in integration.get("conflictResolutionsZh", []) if normalize_spaces(str(item))]
    )
    integration["renderIntentZh"] = normalize_spaces(str(integration.get("renderIntentZh", "")))
    render_blueprint["integration"] = integration

    render_blueprint["acceptanceChecksZh"] = unique_list(
        [normalize_spaces(str(item)) for item in render_blueprint.get("acceptanceChecksZh", []) if normalize_spaces(str(item))]
    )
    render_blueprint["meta"] = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "stage": "render",
    }
    return render_blueprint


def build_render_blueprint(project_dir: Path, bundle, default_run_context: dict[str, Any], character_assets: dict, creative_package: dict[str, Any], model_config_path: Path) -> dict[str, Any]:
    trace_dir = bundle.trace_dir / "llm"
    result = call_json_task(
        project_dir=project_dir,
        model_config_path=model_config_path,
        system_prompt=_system_prompt(project_dir, render_blueprint_contract()),
        user_payload=to_deepseek_payload(
            {
                "defaultRunContext": default_run_context,
                "subjectProfile": character_assets["subjectProfile"],
                "worldDesign": creative_package["worldDesign"],
                "actionDesign": creative_package["actionDesign"],
                "wardrobeDesign": creative_package["wardrobeDesign"],
                "cameraDesign": creative_package["cameraDesign"],
            }
        ),
        trace_request_path=trace_dir / "05_render_director.request.json",
        trace_response_path=trace_dir / "05_render_director.response.json",
    )
    render_blueprint = _normalize_render_blueprint(from_deepseek_payload(result))
    write_json(bundle.render_dir / "render_blueprint.json", render_blueprint)
    return render_blueprint
