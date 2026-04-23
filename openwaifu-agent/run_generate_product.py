from __future__ import annotations

"""只运行生成层产品链路的单次测试脚本，不进入发布层。"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from product_pipeline import run_generation_product_pipeline
from runtime_layout import create_run_bundle, delete_run_bundle


def configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def log(message: str) -> None:
    print(f"[generate] {message}", flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one generation-only product pipeline without publish."
    )
    parser.add_argument("--run-label", default="generate")
    return parser


def run_single(run_label: str) -> int:
    bundle = create_run_bundle(PROJECT_DIR, "generate", run_label)
    try:
        result = run_generation_product_pipeline(
            PROJECT_DIR,
            bundle,
            log=log,
            generation_owner={
                "ownerType": "run_generate_product",
                "ownerLabel": "run_generate_product.py",
                "runId": bundle.run_id,
                "metadata": {
                    "command": "single",
                },
            },
        )
        summary = result["summary"]
        log(f"Run dir: {bundle.root}")
        log(f"Creative package: {summary['creativePackagePath']}")
        log(f"Social post package: {summary['socialPostPackagePath']}")
        log(f"Prompt package: {summary['promptPackagePath']}")
        log(f"Execution package: {summary['executionPackagePath']}")
        log(f"Generated image: {summary['generatedImagePath']}")
        log(f"Summary: {bundle.output_dir / 'run_summary.json'}")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        delete_run_bundle(bundle)
        raise


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    return run_single(args.run_label)


if __name__ == "__main__":
    raise SystemExit(main())
