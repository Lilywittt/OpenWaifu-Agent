from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from io_utils import read_json, write_json


def write_seed_source(render_blueprint: dict) -> int:
    raw = str(render_blueprint).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:12], 16)


def _fact_map(render_blueprint: dict) -> dict[str, dict[str, str]]:
    mapping: dict[str, dict[str, str]] = {}
    for section in ("subject", "world", "action", "camera"):
        for item in render_blueprint.get(section, {}).get("facts", []):
            mapping[item["id"]] = {"section": section, "textZh": item["textZh"]}
        for item in render_blueprint.get(section, {}).get("forbidden", []):
            mapping[item["id"]] = {"section": f"{section}_forbidden", "textZh": item["textZh"]}
    for item in render_blueprint.get("wardrobe", {}).get("required", []):
        mapping[item["id"]] = {"section": "wardrobe", "textZh": item["textZh"]}
    for item in render_blueprint.get("wardrobe", {}).get("optional", []):
        mapping[item["id"]] = {"section": "wardrobe_optional", "textZh": item["textZh"]}
    for item in render_blueprint.get("wardrobe", {}).get("forbidden", []):
        mapping[item["id"]] = {"section": "wardrobe_forbidden", "textZh": item["textZh"]}
    return mapping


def _ordered_positive_facts(render_blueprint: dict) -> list[dict[str, str]]:
    fact_map = _fact_map(render_blueprint)
    integration = render_blueprint.get("integration", {})
    ordered_ids: list[str] = []
    for key in ("heroFactIds", "supportingFactIds"):
        for fact_id in integration.get(key, []):
            if fact_id in fact_map and fact_id not in ordered_ids:
                ordered_ids.append(fact_id)
    for section in ("subject", "world", "action", "camera"):
        for item in render_blueprint.get(section, {}).get("facts", []):
            if item["id"] not in ordered_ids:
                ordered_ids.append(item["id"])
    for item in render_blueprint.get("wardrobe", {}).get("required", []):
        if item["id"] not in ordered_ids:
            ordered_ids.append(item["id"])
    for item in render_blueprint.get("wardrobe", {}).get("optional", []):
        if item["id"] not in ordered_ids:
            ordered_ids.append(item["id"])
    return [{"id": fact_id, **fact_map[fact_id]} for fact_id in ordered_ids]


def _ordered_negative_facts(render_blueprint: dict) -> list[dict[str, str]]:
    fact_map = _fact_map(render_blueprint)
    integration = render_blueprint.get("integration", {})
    ordered_ids: list[str] = []
    for fact_id in integration.get("negativeFactIds", []):
        if fact_id in fact_map and fact_id not in ordered_ids:
            ordered_ids.append(fact_id)
    for section in ("subject", "world", "action", "camera"):
        for item in render_blueprint.get(section, {}).get("forbidden", []):
            if item["id"] not in ordered_ids:
                ordered_ids.append(item["id"])
    for item in render_blueprint.get("wardrobe", {}).get("forbidden", []):
        if item["id"] not in ordered_ids:
            ordered_ids.append(item["id"])
    return [{"id": fact_id, **fact_map[fact_id]} for fact_id in ordered_ids]


def build_render_packet(project_dir: Path, bundle, render_blueprint: dict) -> dict[str, Any]:
    runtime_profile = read_json(project_dir / "config" / "runtime_profile.json")
    render_policy = read_json(project_dir / runtime_profile["renderPromptPolicyPath"].replace("./", ""))
    render_packet = {
        "summaryZh": render_blueprint.get("summaryZh", ""),
        "aspectRatio": render_blueprint.get("camera", {}).get("aspectRatio", "4:5"),
        "framing": render_blueprint.get("camera", {}).get("framing", "full_body"),
        "positiveFacts": _ordered_positive_facts(render_blueprint),
        "negativeFacts": _ordered_negative_facts(render_blueprint),
        "stylePositiveEn": render_policy.get("stylePositiveEn", []),
        "genericNegativeEn": render_policy.get("genericNegativeEn", []),
        "workflow": {
            "provider": runtime_profile["defaultProvider"],
            "seed": write_seed_source(render_blueprint),
        },
    }
    write_json(bundle.render_dir / "render_packet.json", render_packet)
    return render_packet
