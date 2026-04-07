from __future__ import annotations

"""只运行生成层产品链路的单次测试脚本，不进入发布层。"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
TOOLS_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
for import_path in (TOOLS_DIR, SRC_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from common import configure_utf8_stdio

from product_pipeline import run_generation_product_pipeline
from runtime_layout import create_run_bundle, delete_run_bundle


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
        result = run_generation_product_pipeline(PROJECT_DIR, bundle, log=log)
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
