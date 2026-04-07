from __future__ import annotations

"""从已有 creative 产物直接回放 prompt_builder 与 execution 的测试脚本。"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[2]
TOOLS_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
for import_path in (TOOLS_DIR, SRC_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from common import (
    build_batch_dir,
    configure_utf8_stdio,
    create_sample_bundle,
    resolve_creative_package_paths,
)

from character_assets import load_character_assets
from creative import build_default_run_context
from execution import run_execution_pipeline
from io_utils import ensure_dir, read_json, write_json, write_text
from prompt_builder import run_prompt_builder_pipeline


BATCH_KIND = "prompt_execution_from_creative"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run prompt_builder and execution directly from existing creative outputs."
    )
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--label", default="batch")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--source-batch", default="")
    return parser

def materialize_creative_snapshot(bundle, creative_package: dict[str, Any]) -> None:
    write_json(bundle.creative_dir / "05_creative_package.json", creative_package)

    social_signal_sample = creative_package.get("socialSignalSample")
    if isinstance(social_signal_sample, dict) and social_signal_sample:
        write_json(bundle.creative_dir / "00_social_signal_filter.json", social_signal_sample)

    world_design = creative_package.get("worldDesign", {})
    if isinstance(world_design, dict):
        write_json(bundle.creative_dir / "01_world_design.json", world_design)

    for filename, key in (
        ("02_environment_design.md", "environmentDesign"),
        ("03_styling_design.md", "stylingDesign"),
        ("04_action_design.md", "actionDesign"),
    ):
        text = str(creative_package.get(key, "")).strip()
        if text:
            write_text(bundle.creative_dir / filename, text + "\n")


def build_record(sample_dir: Path) -> dict[str, Any]:
    source_meta = read_json(sample_dir / "input" / "creative_source.json")
    creative_package = read_json(sample_dir / "creative" / "05_creative_package.json")
    prompt_package = read_json(sample_dir / "prompt_builder" / "01_prompt_package.json")
    execution_package = read_json(sample_dir / "execution" / "04_execution_package.json")
    return {
        "sampleId": sample_dir.name,
        "source": source_meta,
        "sceneDraft": creative_package.get("worldDesign", {}),
        "environmentDesign": str(creative_package.get("environmentDesign", "")).strip(),
        "stylingDesign": str(creative_package.get("stylingDesign", "")).strip(),
        "actionDesign": str(creative_package.get("actionDesign", "")).strip(),
        "positivePrompt": str(prompt_package.get("positivePrompt", "")).strip(),
        "negativePrompt": str(prompt_package.get("negativePrompt", "")).strip(),
        "generatedImagePath": str(execution_package.get("imagePath", "")).strip(),
    }


def write_summary(batch_dir: Path) -> dict[str, Any]:
    samples_dir = batch_dir / "samples"
    records = [
        build_record(sample_dir)
        for sample_dir in sorted([path for path in samples_dir.iterdir() if path.is_dir()], key=lambda path: path.name)
    ]
    summary = {
        "batchDir": str(batch_dir),
        "sampleCount": len(records),
        "samples": records,
    }
    write_json(batch_dir / "batch_summary.json", summary)

    lines = [
        "# 已有设计稿直跑中下游测试结果",
        "",
        f"- 批次目录: `{batch_dir}`",
        f"- 样本数: {len(records)}",
        "",
    ]
    for record in records:
        lines.append(f"## {record['sampleId']}")
        lines.append(f"- 来源 creative package: `{record['source']['creativePackagePath']}`")
        lines.append(f"- 场景命题: {record['sceneDraft'].get('scenePremiseZh', '')}")
        for title, key in (
            ("环境、布景与光影设计", "environmentDesign"),
            ("服装与造型设计", "stylingDesign"),
            ("动作与姿态、神态设计", "actionDesign"),
        ):
            lines.append(f"### {title}")
            lines.append("```text")
            lines.append(record[key])
            lines.append("```")
        lines.append("### 正向 Prompt")
        lines.append("```text")
        lines.append(record["positivePrompt"])
        lines.append("```")
        lines.append("### 负向 Prompt")
        lines.append("```text")
        lines.append(record["negativePrompt"])
        lines.append("```")
        lines.append(f"- 生成图片: `{record['generatedImagePath']}`")
        lines.append("")
    write_text(batch_dir / "complete_results.md", "\n".join(lines))
    return summary


def run_batch(*, count: int, label: str, sources: list[str], source_batch: str) -> Path:
    creative_package_paths = resolve_creative_package_paths(
        sources=sources,
        source_batch=source_batch,
        count=count,
    )
    batch_dir = build_batch_dir(BATCH_KIND, f"{label}_batch{len(creative_package_paths)}")
    samples_dir = batch_dir / "samples"
    ensure_dir(samples_dir)

    character_assets = load_character_assets(PROJECT_DIR)
    model_config_path = PROJECT_DIR / "config" / "creative_model.json"
    execution_profile_path = PROJECT_DIR / "config" / "execution" / "comfyui_local_animagine_xl.json"
    write_json(
        batch_dir / "batch_meta.json",
        {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "count": len(creative_package_paths),
            "creativePackagePaths": [str(path) for path in creative_package_paths],
        },
    )

    for index, creative_package_path in enumerate(creative_package_paths, start=1):
        sample_root = samples_dir / f"{index:02d}"
        bundle = create_sample_bundle(sample_root, index)
        try:
            creative_package = read_json(creative_package_path)
            default_run_context = creative_package.get("defaultRunContext") or build_default_run_context(
                now_local=datetime.now().isoformat(timespec="seconds"),
            )
            write_json(bundle.input_dir / "default_run_context.json", default_run_context)
            write_json(bundle.input_dir / "character_assets_snapshot.json", character_assets)
            write_json(
                bundle.input_dir / "creative_source.json",
                {
                    "creativePackagePath": str(creative_package_path),
                },
            )
            materialize_creative_snapshot(bundle, creative_package)
            prompt_package = run_prompt_builder_pipeline(
                PROJECT_DIR,
                bundle,
                default_run_context,
                character_assets,
                creative_package,
                model_config_path,
            )
            run_execution_pipeline(
                PROJECT_DIR,
                bundle,
                default_run_context,
                prompt_package,
                execution_profile_path,
            )
        except Exception:
            shutil.rmtree(sample_root, ignore_errors=True)
            raise

    write_summary(batch_dir)
    return batch_dir


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    batch_dir = run_batch(
        count=args.count,
        label=args.label,
        sources=args.source,
        source_batch=args.source_batch,
    )
    print(batch_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
