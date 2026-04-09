from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from io_utils import read_json
from product_pipeline import run_full_product_pipeline
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
    single.add_argument("--publish-target", action="append", default=[])

    subparsers.add_parser("review", help="Print the latest run summary.")
    subparsers.add_parser("paths", help="Print the runtime root and latest bundle file.")
    return parser


def normalize_argv(argv: list[str]) -> list[str]:
    if not argv:
        return ["single"]
    if argv[0].startswith("-") or argv[0] not in {"single", "review", "paths"}:
        return ["single", *argv]
    return argv


def run_single(args) -> int:
    mode_label = "default"
    bundle = create_run_bundle(PROJECT_DIR, mode_label, args.run_label or mode_label)
    try:
        result = run_full_product_pipeline(
            PROJECT_DIR,
            bundle,
            log=log,
            publish_target_ids=args.publish_target or None,
        )
        summary = result["summary"]
        latest_path = update_latest(
            PROJECT_DIR,
            bundle,
            {
                "runId": bundle.run_id,
                "creativePackagePath": summary["creativePackagePath"],
                "socialPostPackagePath": summary["socialPostPackagePath"],
                "promptPackagePath": summary["promptPackagePath"],
                "executionPackagePath": summary["executionPackagePath"],
                "publishPackagePath": summary["publishPackagePath"],
                "summaryPath": str(bundle.output_dir / "run_summary.json"),
                "sceneDraftPremiseZh": summary["sceneDraftPremiseZh"],
            },
        )

        log(f"Run dir: {bundle.root}")
        log(f"Creative package: {summary['creativePackagePath']}")
        log(f"Social post package: {summary['socialPostPackagePath']}")
        log(f"Prompt package: {summary['promptPackagePath']}")
        log(f"Execution package: {summary['executionPackagePath']}")
        log(f"Publish package: {summary['publishPackagePath']}")
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
    social_post_package_path = Path(latest["summary"]["socialPostPackagePath"])
    prompt_package_path = Path(latest["summary"]["promptPackagePath"])
    execution_package_path = Path(latest["summary"]["executionPackagePath"])
    publish_package_path = Path(latest["summary"]["publishPackagePath"])
    payload = {
        "latest": latest,
        "summary": read_json(summary_path),
        "creativePackage": read_json(creative_package_path),
        "socialPostPackage": read_json(social_post_package_path),
        "promptPackage": read_json(prompt_package_path),
        "executionPackage": read_json(execution_package_path),
        "publishPackage": read_json(publish_package_path),
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
