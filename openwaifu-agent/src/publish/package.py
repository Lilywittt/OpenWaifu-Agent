from __future__ import annotations

from pathlib import Path
from typing import Any


def _detect_image_mime(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "application/octet-stream"


def _normalize_social_tags(raw_tags: Any) -> list[str]:
    if not isinstance(raw_tags, list):
        return []
    output: list[str] = []
    seen: set[str] = set()
    for item in raw_tags:
        tag = str(item or "").replace("#", "").strip()
        tag = " ".join(tag.split())
        key = tag.casefold()
        if not tag or key in seen:
            continue
        output.append(tag[:40])
        seen.add(key)
        if len(output) >= 8:
            break
    return output


def build_publish_input(
    *,
    bundle,
    character_assets: dict[str, Any],
    creative_package: dict[str, Any],
    social_post_package: dict[str, Any],
    execution_package: dict[str, Any],
) -> dict[str, Any]:
    subject_profile = character_assets.get("subjectProfile", {})
    world_design = creative_package.get("worldDesign", {})
    image_path = Path(str(execution_package.get("imagePath", "")).strip())
    if not image_path.exists():
        raise RuntimeError(f"execution package image path does not exist: {image_path}")

    social_post_text = str(social_post_package.get("socialPostText", "")).strip()
    if not social_post_text:
        raise RuntimeError("social post package did not contain socialPostText.")

    return {
        "runId": bundle.run_id,
        "subjectId": str(subject_profile.get("subject_id", "")).strip(),
        "subjectDisplayNameZh": str(subject_profile.get("display_name_zh", "")).strip(),
        "scenePremiseZh": str(world_design.get("scenePremiseZh", "")).strip(),
        "sceneDraftTextZh": str(world_design.get("worldSceneZh", "")).strip(),
        "socialPostText": social_post_text,
        "socialTags": _normalize_social_tags(social_post_package.get("socialTags", [])),
        "imagePath": str(image_path),
        "imageMime": _detect_image_mime(image_path),
        "generatedAt": str(execution_package.get("meta", {}).get("createdAt", "")).strip(),
        "source": {
            "creativePackagePath": str(bundle.creative_dir / "05_creative_package.json"),
            "socialPostPackagePath": str(bundle.social_post_dir / "01_social_post_package.json"),
            "executionPackagePath": str(bundle.execution_dir / "04_execution_package.json"),
        },
    }
