from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from character_assets import load_character_assets
from creative import build_default_run_context, run_creative_pipeline
from execution import run_execution_pipeline
from io_utils import write_json
from prompt_builder import run_prompt_builder_pipeline
from publish import run_publish_pipeline
from social_post import run_social_post_pipeline


def write_generation_summary(
    bundle,
    creative_package: dict[str, Any],
    social_post_package: dict[str, Any],
    prompt_package: dict[str, Any],
    execution_package: dict[str, Any],
) -> dict[str, Any]:
    summary = {
        "runId": bundle.run_id,
        "creativePackagePath": str(bundle.creative_dir / "05_creative_package.json"),
        "socialPostPackagePath": str(bundle.social_post_dir / "01_social_post_package.json"),
        "promptPackagePath": str(bundle.prompt_builder_dir / "01_prompt_package.json"),
        "imagePromptPath": str(bundle.prompt_builder_dir / "00_image_prompt.json"),
        "executionPackagePath": str(bundle.execution_dir / "04_execution_package.json"),
        "socialSignalSampleZh": creative_package.get("socialSignalSample", {}).get("sampledSignalsZh", []),
        "sceneDraftPremiseZh": creative_package.get("worldDesign", {}).get("scenePremiseZh", ""),
        "sceneDraftTextZh": creative_package.get("worldDesign", {}).get("worldSceneZh", ""),
        "socialPostText": str(social_post_package.get("socialPostText", "")).strip(),
        "socialPostOutputPath": str(bundle.output_dir / "social_post.txt"),
        "environmentDesignTextZh": str(creative_package.get("environmentDesign", "")).strip(),
        "stylingDesignTextZh": str(creative_package.get("stylingDesign", "")).strip(),
        "actionDesignTextZh": str(creative_package.get("actionDesign", "")).strip(),
        "positivePromptText": str(prompt_package.get("positivePrompt", "")).strip(),
        "negativePromptText": str(prompt_package.get("negativePrompt", "")).strip(),
        "generatedImagePath": str(execution_package.get("imagePath", "")).strip(),
        "checkpointName": str(execution_package.get("checkpointName", "")).strip(),
    }
    write_json(bundle.output_dir / "run_summary.json", summary)
    return summary


def write_full_summary(
    bundle,
    creative_package: dict[str, Any],
    social_post_package: dict[str, Any],
    prompt_package: dict[str, Any],
    execution_package: dict[str, Any],
    publish_package: dict[str, Any],
) -> dict[str, Any]:
    summary = write_generation_summary(
        bundle,
        creative_package,
        social_post_package,
        prompt_package,
        execution_package,
    )
    summary["publishPackagePath"] = str(bundle.publish_dir / "04_publish_package.json")
    summary["publishReceipts"] = publish_package.get("receipts", [])
    write_json(bundle.output_dir / "run_summary.json", summary)
    return summary


def _build_generation_context(project_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    character_assets = load_character_assets(project_dir)
    default_run_context = build_default_run_context(
        now_local=datetime.now().isoformat(timespec="seconds"),
    )
    return character_assets, default_run_context


def run_generation_product_pipeline(
    project_dir: Path,
    bundle,
    *,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    character_assets, default_run_context = _build_generation_context(project_dir)
    write_json(bundle.input_dir / "default_run_context.json", default_run_context)
    write_json(bundle.input_dir / "character_assets_snapshot.json", character_assets)

    if log:
        log("creative layer: character assets + social sampling -> scene draft -> three design drafts")
    creative_package = run_creative_pipeline(
        project_dir,
        bundle,
        default_run_context,
        character_assets,
        project_dir / "config" / "creative_model.json",
    )

    if log:
        log("social post layer: character assets + scene draft -> social post text")
    social_post_package = run_social_post_pipeline(
        project_dir,
        bundle,
        default_run_context,
        character_assets,
        creative_package,
        project_dir / "config" / "creative_model.json",
    )

    if log:
        log("prompt builder layer: character assets + three design drafts -> image prompt")
    prompt_package = run_prompt_builder_pipeline(
        project_dir,
        bundle,
        default_run_context,
        character_assets,
        creative_package,
        project_dir / "config" / "creative_model.json",
    )

    if log:
        log("execution layer: image prompt -> ComfyUI workflow -> generated image")
    execution_package = run_execution_pipeline(
        project_dir,
        bundle,
        default_run_context,
        prompt_package,
        project_dir / "config" / "execution" / "comfyui_local_animagine_xl.json",
    )

    summary = write_generation_summary(
        bundle,
        creative_package,
        social_post_package,
        prompt_package,
        execution_package,
    )
    return {
        "characterAssets": character_assets,
        "defaultRunContext": default_run_context,
        "creativePackage": creative_package,
        "socialPostPackage": social_post_package,
        "promptPackage": prompt_package,
        "executionPackage": execution_package,
        "summary": summary,
    }


def run_full_product_pipeline(
    project_dir: Path,
    bundle,
    *,
    log: Callable[[str], None] | None = None,
    publish_target_ids: list[str] | None = None,
) -> dict[str, Any]:
    result = run_generation_product_pipeline(
        project_dir,
        bundle,
        log=log,
    )

    if log:
        log("publish layer: image + social post -> publish targets")
    publish_package = run_publish_pipeline(
        project_dir,
        bundle,
        result["defaultRunContext"],
        result["characterAssets"],
        result["creativePackage"],
        result["socialPostPackage"],
        result["executionPackage"],
        target_ids=publish_target_ids,
    )

    summary = write_full_summary(
        bundle,
        result["creativePackage"],
        result["socialPostPackage"],
        result["promptPackage"],
        result["executionPackage"],
        publish_package,
    )

    result["publishPackage"] = publish_package
    result["summary"] = summary
    return result
