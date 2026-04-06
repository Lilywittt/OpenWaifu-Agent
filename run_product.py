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
from comfyui_engine import build_workflow_request, run_generation
from creative import build_default_run_context, run_creative_pipeline
from io_utils import read_json, write_json
from render import build_render_blueprint, build_render_packet, compile_prompt_bundle
from review import build_review
from runtime_layout import create_run_bundle, delete_run_bundle, runtime_root, update_latest


def configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def log(message: str) -> None:
    print(f"[v3] {message}", flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IG Roleplay v3 unified product entrypoint.")
    subparsers = parser.add_subparsers(dest="command")

    single = subparsers.add_parser("single", help="Run one v3 product image.")
    single.add_argument("--provider", default="")
    single.add_argument("--run-label", default="")
    single.add_argument("--comfyui-endpoint", default="")
    single.add_argument("--no-auto-start-comfyui", action="store_true")

    subparsers.add_parser("review", help="Print the latest v3 review bundle.")
    subparsers.add_parser("paths", help="Print the runtime root and latest bundle file.")
    return parser


def normalize_argv(argv: list[str]) -> list[str]:
    if not argv:
        return ["single"]
    if argv[0].startswith("-") or argv[0] not in {"single", "review", "paths"}:
        return ["single", *argv]
    return argv


def run_single(args) -> int:
    runtime_profile = read_json(PROJECT_DIR / "config" / "runtime_profile.json")
    provider = args.provider or runtime_profile["defaultProvider"]
    mode_label = "default"
    bundle = create_run_bundle(PROJECT_DIR, mode_label, args.run_label or mode_label)
    try:
        character_assets = load_character_assets(PROJECT_DIR)
        default_run_context = build_default_run_context(
            now_local=datetime.now().isoformat(timespec="seconds"),
        )
        write_json(bundle.input_dir / "default_run_context.json", default_run_context)
        write_json(bundle.input_dir / "character_assets_snapshot.json", character_assets)

        log("creative layer: scene draft -> scene-to-design")
        creative_package = run_creative_pipeline(
            PROJECT_DIR,
            bundle,
            default_run_context,
            character_assets,
            PROJECT_DIR / "config" / "creative_model.json",
        )

        log("render layer: render director -> render packet -> prompt bundle -> workflow request")
        render_blueprint = build_render_blueprint(
            PROJECT_DIR,
            bundle,
            default_run_context,
            character_assets,
            creative_package,
            PROJECT_DIR / "config" / "creative_model.json",
        )
        render_packet = build_render_packet(PROJECT_DIR, bundle, render_blueprint)
        prompt_bundle = compile_prompt_bundle(PROJECT_DIR, bundle, render_packet)
        workflow_bundle = build_workflow_request(PROJECT_DIR, bundle, render_packet, prompt_bundle, provider, args.comfyui_endpoint)

        log("running local ComfyUI generation")
        generation_result = run_generation(
            PROJECT_DIR,
            bundle,
            workflow_bundle,
            args.comfyui_endpoint,
            auto_start=not args.no_auto_start_comfyui,
        )

        review = build_review(bundle, creative_package, render_blueprint, render_packet, prompt_bundle, generation_result)
        latest_path = update_latest(
            PROJECT_DIR,
            bundle,
            {
                "runId": bundle.run_id,
                "imagePath": generation_result["imagePath"],
                "reviewPath": str(bundle.output_dir / "review.json"),
            },
        )

        log(f"Run dir: {bundle.root}")
        log(f"Image: {generation_result['imagePath']}")
        log(f"Review: {bundle.output_dir / 'review.json'}")
        log(f"Latest: {latest_path}")
        print(json.dumps(review, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        delete_run_bundle(bundle)
        raise


def review_latest() -> int:
    latest_path = runtime_root(PROJECT_DIR) / "latest.json"
    if not latest_path.exists():
        raise RuntimeError("No latest run exists yet.")
    latest = read_json(latest_path)
    review_path = Path(latest["summary"]["reviewPath"])
    review = read_json(review_path)
    print(json.dumps({"latest": latest, "review": review}, ensure_ascii=False, indent=2))
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
