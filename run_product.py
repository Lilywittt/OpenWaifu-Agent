from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from character_assets import load_character_assets
from creative import build_default_run_context, run_creative_pipeline
from execution import run_execution_pipeline
from io_utils import read_json, write_json
from prompt_builder import run_prompt_builder_pipeline
from runtime_layout import create_run_bundle, delete_run_bundle, runtime_root, update_latest


def configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def log(message: str) -> None:
    print(f"[v3] {message}", flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IG Roleplay v3 full creative-to-image entrypoint.")
    subparsers = parser.add_subparsers(dest="command")

    single = subparsers.add_parser("single", help="Run one full upstream-to-image pipeline.")
    single.add_argument("--run-label", default="")

    subparsers.add_parser("review", help="Print the latest run summary.")
    subparsers.add_parser("paths", help="Print the runtime root and latest bundle file.")
    return parser


def normalize_argv(argv: list[str]) -> list[str]:
    if not argv:
        return ["single"]
    if argv[0].startswith("-") or argv[0] not in {"single", "review", "paths"}:
        return ["single", *argv]
    return argv


def _build_run_summary(bundle, creative_package: dict, prompt_package: dict, execution_package: dict) -> dict:
    summary = {
        "runId": bundle.run_id,
        "creativePackagePath": str(bundle.creative_dir / "05_creative_package.json"),
        "promptPackagePath": str(bundle.prompt_builder_dir / "01_prompt_package.json"),
        "imagePromptPath": str(bundle.prompt_builder_dir / "00_image_prompt.json"),
        "executionPackagePath": str(bundle.execution_dir / "04_execution_package.json"),
        "socialSignalSampleZh": creative_package.get("socialSignalSample", {}).get("sampledSignalsZh", []),
        "sceneDraftPremiseZh": creative_package.get("worldDesign", {}).get("scenePremiseZh", ""),
        "sceneDraftTextZh": creative_package.get("worldDesign", {}).get("worldSceneZh", ""),
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


def run_single(args) -> int:
    mode_label = "default"
    bundle = create_run_bundle(PROJECT_DIR, mode_label, args.run_label or mode_label)
    try:
        character_assets = load_character_assets(PROJECT_DIR)
        default_run_context = build_default_run_context(
            now_local=datetime.now().isoformat(timespec="seconds"),
        )
        write_json(bundle.input_dir / "default_run_context.json", default_run_context)
        write_json(bundle.input_dir / "character_assets_snapshot.json", character_assets)

        log("creative layer: 人物原始资产 + 外部发散变量采样层 -> 场景设计稿 -> 环境、布景与光影设计+服装与造型设计+动作与姿态、神态设计")
        creative_package = run_creative_pipeline(
            PROJECT_DIR,
            bundle,
            default_run_context,
            character_assets,
            PROJECT_DIR / "config" / "creative_model.json",
        )

        log("prompt builder layer: 原始人物资产 + 三份设计 -> 生图Prompt")
        prompt_package = run_prompt_builder_pipeline(
            PROJECT_DIR,
            bundle,
            default_run_context,
            character_assets,
            creative_package,
            PROJECT_DIR / "config" / "creative_model.json",
        )

        log("execution layer: 生图Prompt -> ComfyUI workflow -> generated image")
        execution_package = run_execution_pipeline(
            PROJECT_DIR,
            bundle,
            default_run_context,
            prompt_package,
            PROJECT_DIR / "config" / "execution" / "comfyui_local_animagine_xl.json",
        )

        summary = _build_run_summary(bundle, creative_package, prompt_package, execution_package)
        latest_path = update_latest(
            PROJECT_DIR,
            bundle,
            {
                "runId": bundle.run_id,
                "creativePackagePath": summary["creativePackagePath"],
                "promptPackagePath": summary["promptPackagePath"],
                "executionPackagePath": summary["executionPackagePath"],
                "summaryPath": str(bundle.output_dir / "run_summary.json"),
                "sceneDraftPremiseZh": summary["sceneDraftPremiseZh"],
            },
        )

        log(f"Run dir: {bundle.root}")
        log(f"Creative package: {summary['creativePackagePath']}")
        log(f"Prompt package: {summary['promptPackagePath']}")
        log(f"Execution package: {summary['executionPackagePath']}")
        log(f"Generated image: {summary['generatedImagePath']}")
        log(f"Summary: {bundle.output_dir / 'run_summary.json'}")
        log(f"Latest: {latest_path}")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        delete_run_bundle(bundle)
        raise


def review_latest() -> int:
    latest_path = runtime_root(PROJECT_DIR) / "latest.json"
    if not latest_path.exists():
        raise RuntimeError("No latest run exists yet.")
    latest = read_json(latest_path)
    summary_path = Path(latest["summary"]["summaryPath"])
    creative_package_path = Path(latest["summary"]["creativePackagePath"])
    prompt_package_path = Path(latest["summary"]["promptPackagePath"])
    execution_package_path = Path(latest["summary"]["executionPackagePath"])
    payload = {
        "latest": latest,
        "summary": read_json(summary_path),
        "creativePackage": read_json(creative_package_path),
        "promptPackage": read_json(prompt_package_path),
        "executionPackage": read_json(execution_package_path),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def show_paths() -> int:
    print(runtime_root(PROJECT_DIR))
    print(runtime_root(PROJECT_DIR) / "latest.json")
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(normalize_argv(sys.argv[1:] if argv is None else argv))
    if args.command == "single":
        return run_single(args)
    if args.command == "review":
        return review_latest()
    if args.command == "paths":
        return show_paths()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
