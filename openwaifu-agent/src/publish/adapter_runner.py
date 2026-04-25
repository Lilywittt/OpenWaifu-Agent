from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from io_utils import read_json, write_json

from .adapters import get_publish_adapter


def configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _bundle_from_payload(payload: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        run_id=str(payload.get("runId", "")),
        creative_dir=Path(str(payload.get("creativeDir", ""))),
        social_post_dir=Path(str(payload.get("socialPostDir", ""))),
        execution_dir=Path(str(payload.get("executionDir", ""))),
        publish_dir=Path(str(payload.get("publishDir", ""))),
        output_dir=Path(str(payload.get("outputDir", ""))),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one publish adapter in an isolated Python process.")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--receipt", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    project_dir = Path(args.project_dir).resolve()
    request_path = Path(args.request).resolve()
    receipt_path = Path(args.receipt).resolve()
    payload = read_json(request_path)
    if not isinstance(payload, dict):
        raise RuntimeError("发布适配器请求格式无效。")
    target = payload.get("target", {})
    publish_input = payload.get("publishInput", {})
    bundle_payload = payload.get("bundle", {})
    if not isinstance(target, dict) or not isinstance(publish_input, dict) or not isinstance(bundle_payload, dict):
        raise RuntimeError("发布适配器请求缺少 target、publishInput 或 bundle。")
    adapter = get_publish_adapter(str(target.get("adapter", "")).strip())
    receipt = adapter(
        project_dir=project_dir,
        bundle=_bundle_from_payload(bundle_payload),
        target_id=str(target.get("targetId", "")).strip(),
        target_config=target,
        publish_input=publish_input,
    )
    write_json(receipt_path, receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
