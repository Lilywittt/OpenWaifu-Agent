from __future__ import annotations


def scene_draft_contract() -> dict:
    return {
        "scenePremiseZh": "",
        "worldSceneZh": "",
    }


def action_design_contract() -> dict:
    return {
        "actionSummaryZh": "",
        "momentZh": "",
        "bodyActionZh": "",
        "mustReadZh": [""],
        "forbiddenDriftZh": [""],
        "notesZh": [""],
    }


def wardrobe_design_contract() -> dict:
    return {
        "wardrobeSummaryZh": "",
        "requiredZh": [""],
        "optionalZh": [""],
        "forbiddenZh": [""],
        "notesZh": [""],
    }


def camera_design_contract() -> dict:
    return {
        "cameraSummaryZh": "",
        "framing": "full_body",
        "aspectRatio": "4:5",
        "angleZh": "",
        "compositionGoalZh": "",
        "mustIncludeZh": [""],
        "forbiddenZh": [""],
        "notesZh": [""],
    }


def scene_to_design_contract() -> dict:
    return {
        "actionDesign": action_design_contract(),
        "wardrobeDesign": wardrobe_design_contract(),
        "cameraDesign": camera_design_contract(),
    }
