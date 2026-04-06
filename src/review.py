from __future__ import annotations

from pathlib import Path

from io_utils import write_json, write_text


def _fact_texts(items: list[dict]) -> list[str]:
    return [str(item.get("textZh", "")).strip() for item in items if str(item.get("textZh", "")).strip()]


def build_review(bundle, creative_package: dict, render_blueprint: dict, render_packet: dict, prompt_bundle: dict, generation_result: dict) -> dict:
    image_path = Path(generation_result["imagePath"])
    review = {
        "runId": bundle.run_id,
        "imageReady": image_path.exists(),
        "imagePath": str(image_path),
        "worldDesignSummaryZh": creative_package.get("worldDesign", {}).get("scenePremiseZh", ""),
        "actionDesignSummaryZh": creative_package.get("actionDesign", {}).get("actionSummaryZh", ""),
        "wardrobeDesignSummaryZh": creative_package.get("wardrobeDesign", {}).get("wardrobeSummaryZh", ""),
        "cameraDesignSummaryZh": creative_package.get("cameraDesign", {}).get("cameraSummaryZh", ""),
        "renderSummaryZh": render_blueprint.get("summaryZh", ""),
        "subjectIdentityZh": render_blueprint.get("subject", {}).get("identityReadZh", ""),
        "worldFactsZh": _fact_texts(render_blueprint.get("world", {}).get("facts", [])),
        "actionFactsZh": _fact_texts(render_blueprint.get("action", {}).get("facts", [])),
        "wardrobeFactsZh": _fact_texts(render_blueprint.get("wardrobe", {}).get("required", [])),
        "cameraFactsZh": _fact_texts(render_blueprint.get("camera", {}).get("facts", [])),
        "acceptanceChecksZh": render_blueprint.get("acceptanceChecksZh", []),
        "positivePrompt": prompt_bundle.get("positivePrompt", ""),
        "negativePrompt": prompt_bundle.get("negativePrompt", ""),
        "positiveFactCount": len(render_packet.get("positiveFacts", [])),
        "negativeFactCount": len(render_packet.get("negativeFacts", [])),
    }
    write_json(bundle.output_dir / "review.json", review)
    write_text(
        bundle.output_dir / "review.txt",
        "\n".join(
            [
                f"run_id: {bundle.run_id}",
                f"image_ready: {review['imageReady']}",
                f"image_path: {review['imagePath']}",
                f"world_design: {review['worldDesignSummaryZh']}",
                f"action_design: {review['actionDesignSummaryZh']}",
                f"wardrobe_design: {review['wardrobeDesignSummaryZh']}",
                f"camera_design: {review['cameraDesignSummaryZh']}",
                f"render_summary: {review['renderSummaryZh']}",
                f"subject: {review['subjectIdentityZh']}",
                f"world_facts: {' | '.join(review['worldFactsZh'])}",
                f"action_facts: {' | '.join(review['actionFactsZh'])}",
                f"wardrobe_facts: {' | '.join(review['wardrobeFactsZh'])}",
                f"camera_facts: {' | '.join(review['cameraFactsZh'])}",
            ]
        )
        + "\n",
    )
    return review
