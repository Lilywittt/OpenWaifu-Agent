from __future__ import annotations

"""直接读取指定发布输入包或已有 run 产物并回放发布层的测试脚本。"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[2]
TOOLS_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
for import_path in (TOOLS_DIR, SRC_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from common import build_batch_dir, configure_utf8_stdio, create_sample_bundle

from character_assets import load_character_assets
from creative import build_default_run_context
from io_utils import ensure_dir, read_json, write_json, write_text
from publish import build_publish_input, run_publish_stage


BATCH_KIND = "publish_from_package"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the publish layer directly from an existing publish input package or run directory."
    )
    parser.add_argument("--source", required=True)
    parser.add_argument("--label", default="batch")
    parser.add_argument("--target", action="append", default=[])
    return parser


def _resolve_publish_input_file(source: Path) -> Path | None:
    candidates = [
        source,
        source / "00_publish_input.json",
        source / "publish" / "00_publish_input.json",
    ]
    for candidate in candidates:
        if candidate.is_file() and candidate.name == "00_publish_input.json":
            return candidate.resolve()
    return None


def _is_run_dir(source: Path) -> bool:
    return (
        (source / "creative" / "05_creative_package.json").exists()
        and (source / "social_post" / "01_social_post_package.json").exists()
        and (source / "execution" / "04_execution_package.json").exists()
    )


def resolve_publish_source(source: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    source_path = Path(source).resolve()
    publish_input_file = _resolve_publish_input_file(source_path)
    if publish_input_file is not None:
        publish_input = read_json(publish_input_file)
        default_run_context_path = publish_input_file.parents[1] / "input" / "default_run_context.json"
        default_run_context = (
            read_json(default_run_context_path)
            if default_run_context_path.exists()
            else build_default_run_context(now_local=datetime.now().isoformat(timespec="seconds"))
        )
        return (
            publish_input,
            default_run_context,
            {
                "sourceType": "publish_input",
                "publishInputPath": str(publish_input_file),
            },
        )

    if not source_path.is_dir() or not _is_run_dir(source_path):
        raise RuntimeError(f"Unsupported publish source: {source_path}")

    default_run_context_path = source_path / "input" / "default_run_context.json"
    character_assets_path = source_path / "input" / "character_assets_snapshot.json"
    default_run_context = (
        read_json(default_run_context_path)
        if default_run_context_path.exists()
        else build_default_run_context(now_local=datetime.now().isoformat(timespec="seconds"))
    )
    character_assets = (
        read_json(character_assets_path)
        if character_assets_path.exists()
        else load_character_assets(PROJECT_DIR)
    )
    source_bundle = SimpleNamespace(
        run_id=source_path.name,
        creative_dir=source_path / "creative",
        social_post_dir=source_path / "social_post",
        execution_dir=source_path / "execution",
    )
    publish_input = build_publish_input(
        bundle=source_bundle,
        character_assets=character_assets,
        creative_package=read_json(source_path / "creative" / "05_creative_package.json"),
        social_post_package=read_json(source_path / "social_post" / "01_social_post_package.json"),
        execution_package=read_json(source_path / "execution" / "04_execution_package.json"),
    )
    return (
        publish_input,
        default_run_context,
        {
            "sourceType": "run_dir",
            "runRoot": str(source_path),
        },
    )


def write_summary(batch_dir: Path) -> dict[str, Any]:
    sample_dir = batch_dir / "samples" / "01"
    source_meta = read_json(sample_dir / "input" / "publish_source.json")
    publish_input = read_json(sample_dir / "publish" / "00_publish_input.json")
    publish_package = read_json(sample_dir / "publish" / "04_publish_package.json")
    summary = {
        "batchDir": str(batch_dir),
        "sampleCount": 1,
        "samples": [
            {
                "sampleId": "01",
                "source": source_meta,
                "publishInput": publish_input,
                "receipts": publish_package.get("receipts", []),
            }
        ],
    }
    write_json(batch_dir / "batch_summary.json", summary)

    lines = [
        "# 指定发布包直跑发布层测试结果",
        "",
        f"- 批次目录: `{batch_dir}`",
        "",
        "## 01",
        f"- 来源: `{json.dumps(source_meta, ensure_ascii=False)}`",
        f"- 场景命题: {publish_input.get('scenePremiseZh', '')}",
        "### 社媒文案",
        "```text",
        str(publish_input.get("socialPostText", "")).strip(),
        "```",
        f"- 图片路径: `{publish_input.get('imagePath', '')}`",
        "### 发布回执",
        "```json",
        json.dumps(read_json(sample_dir / "publish" / "04_publish_package.json"), ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    write_text(batch_dir / "complete_results.md", "\n".join(lines))
    return summary


def run_once(*, source: str, label: str, target_ids: list[str]) -> Path:
    publish_input, default_run_context, source_meta = resolve_publish_source(source)
    batch_dir = build_batch_dir(BATCH_KIND, f"{label}_batch1")
    sample_root = batch_dir / "samples" / "01"
    bundle = create_sample_bundle(sample_root, 1)
    try:
        write_json(batch_dir / "batch_meta.json", {"createdAt": datetime.now().isoformat(timespec="seconds"), "source": source})
        write_json(bundle.input_dir / "default_run_context.json", default_run_context)
        write_json(bundle.input_dir / "publish_source.json", source_meta)
        run_publish_stage(
            PROJECT_DIR,
            bundle,
            default_run_context,
            publish_input,
            target_ids=target_ids or None,
        )
    except Exception:
        shutil.rmtree(batch_dir, ignore_errors=True)
        raise
    write_summary(batch_dir)
    return batch_dir


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    batch_dir = run_once(
        source=args.source,
        label=args.label,
        target_ids=args.target,
    )
    print(batch_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
