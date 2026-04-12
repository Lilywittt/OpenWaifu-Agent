from __future__ import annotations

"""从已有采样内容直接运行到生图的批量测试脚本。"""

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

from runner_common import (
    build_batch_dir,
    configure_utf8_stdio,
    create_sample_bundle,
    resolve_world_design_input_paths,
)

from io_utils import ensure_dir, read_json, write_json, write_text
from test_pipeline import (
    END_STAGE_IMAGE,
    SOURCE_KIND_SAMPLE_FILE,
    execute_workbench_task_in_bundle,
)


BATCH_KIND = "sample_to_image"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run world design, three design modules, social post, prompt builder, and execution from existing sampled content."
    )
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--label", default="batch")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--source-batch", default="")
    return parser


def build_record(sample_dir: Path) -> dict[str, Any]:
    source_meta_path = sample_dir / "input" / "content_workbench_source.json"
    if not source_meta_path.exists():
        source_meta_path = sample_dir / "input" / "sample_source.json"
    source_meta = read_json(source_meta_path)
    source_snapshot = read_json(sample_dir / "input" / "social_signal_sample_snapshot.json")
    creative_package = read_json(sample_dir / "creative" / "05_creative_package.json")
    social_post_package = read_json(sample_dir / "social_post" / "01_social_post_package.json")
    summary = read_json(sample_dir / "output" / "run_summary.json")
    execution_package = read_json(sample_dir / "execution" / "04_execution_package.json")
    return {
        "sampleId": sample_dir.name,
        "source": source_meta,
        "socialSignalSample": source_snapshot,
        "sceneDraft": creative_package.get("worldDesign", {}),
        "environmentDesign": str(creative_package.get("environmentDesign", "")).strip(),
        "stylingDesign": str(creative_package.get("stylingDesign", "")).strip(),
        "actionDesign": str(creative_package.get("actionDesign", "")).strip(),
        "socialPostText": str(social_post_package.get("socialPostText", "")).strip(),
        "positivePrompt": str(summary.get("positivePromptText", "")).strip(),
        "negativePrompt": str(summary.get("negativePromptText", "")).strip(),
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
        "# 已有采样内容直跑到生图的测试结果",
        "",
        f"- 批次目录: `{batch_dir}`",
        f"- 样本数: {len(records)}",
        "",
    ]
    for record in records:
        social = record["socialSignalSample"]
        lines.append(f"## {record['sampleId']}")
        lines.append(f"- 来源采样输入: `{record['source'].get('sourcePath', record['source'].get('worldDesignInputPath', ''))}`")
        lines.append(f"- 采样来源: {social.get('sourceZh', '')} / {social.get('providerZh', '')}")
        lines.append("### 采样内容")
        lines.append("```json")
        lines.append(str(social))
        lines.append("```")
        lines.append(f"- 场景命题: {record['sceneDraft'].get('scenePremiseZh', '')}")
        lines.append("### 环境、布景与光影设计")
        lines.append("```text")
        lines.append(record["environmentDesign"])
        lines.append("```")
        lines.append("### 服装与造型设计")
        lines.append("```text")
        lines.append(record["stylingDesign"])
        lines.append("```")
        lines.append("### 动作与姿态、神态设计")
        lines.append("```text")
        lines.append(record["actionDesign"])
        lines.append("```")
        lines.append("### 社媒文案")
        lines.append("```text")
        lines.append(record["socialPostText"])
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
    world_design_input_paths = resolve_world_design_input_paths(
        sources=sources,
        source_batch=source_batch,
        count=count,
    )
    batch_dir = build_batch_dir(BATCH_KIND, f"{label}_batch{len(world_design_input_paths)}")
    samples_dir = batch_dir / "samples"
    ensure_dir(samples_dir)

    write_json(
        batch_dir / "batch_meta.json",
        {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "count": len(world_design_input_paths),
            "worldDesignInputPaths": [str(path) for path in world_design_input_paths],
        },
    )

    for index, world_design_input_path in enumerate(world_design_input_paths, start=1):
        sample_root = samples_dir / f"{index:02d}"
        bundle = create_sample_bundle(sample_root, index)
        try:
            execute_workbench_task_in_bundle(
                PROJECT_DIR,
                bundle,
                {
                    "sourceKind": SOURCE_KIND_SAMPLE_FILE,
                    "endStage": END_STAGE_IMAGE,
                    "label": f"{BATCH_KIND}_{index:02d}",
                    "sourcePath": str(world_design_input_path),
                },
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
