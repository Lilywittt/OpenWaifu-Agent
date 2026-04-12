from __future__ import annotations

"""从已有场景设计稿回放三份下游设计稿的批量测试脚本。"""

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
    resolve_scene_draft_paths,
)

from io_utils import ensure_dir, read_json, read_text, write_json, write_text
from test_pipeline import (
    END_STAGE_DESIGN,
    SOURCE_KIND_SCENE_DRAFT_FILE,
    execute_workbench_task_in_bundle,
)


BATCH_KIND = "scene_draft_downstream"
STAGE_FILES = {
    "environmentDesign": "02_environment_design.md",
    "stylingDesign": "03_styling_design.md",
    "actionDesign": "04_action_design.md",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the three downstream creative modules from existing scene drafts.")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--label", default="batch")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--source-batch", default="")
    return parser


def build_record(sample_dir: Path) -> dict[str, Any]:
    scene_draft = read_json(sample_dir / "creative" / "01_world_design.json")
    stage_outputs = {
        key: read_text(sample_dir / "creative" / filename).strip()
        for key, filename in STAGE_FILES.items()
    }
    source_meta_path = sample_dir / "input" / "content_workbench_source.json"
    if not source_meta_path.exists():
        source_meta_path = sample_dir / "input" / "scene_draft_source.json"
    source_meta = read_json(source_meta_path)
    return {
        "sampleId": sample_dir.name,
        "sceneDraftSource": source_meta,
        "sceneDraft": scene_draft,
        **stage_outputs,
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
        "# 场景设计稿下游三模块测试结果",
        "",
        f"- 批次目录: `{batch_dir}`",
        f"- 样本数: {len(records)}",
        "",
    ]
    for record in records:
        lines.append(f"## {record['sampleId']}")
        lines.append(f"- 场景设计稿来源: `{record['sceneDraftSource'].get('sourcePath', record['sceneDraftSource'].get('sceneDraftPath', ''))}`")
        lines.append(f"- 场景命题: {record['sceneDraft'].get('scenePremiseZh', '')}")
        lines.append("- 场景正文:")
        lines.append("```text")
        lines.append(record["sceneDraft"].get("worldSceneZh", ""))
        lines.append("```")
        for title, key in (
            ("环境、布景与光影设计", "environmentDesign"),
            ("服装与造型设计", "stylingDesign"),
            ("动作与姿态、神态设计", "actionDesign"),
        ):
            lines.append(f"### {title}")
            lines.append("```text")
            lines.append(record[key])
            lines.append("```")
        lines.append("")
    write_text(batch_dir / "complete_results.md", "\n".join(lines))
    return summary


def run_batch(*, count: int, label: str, sources: list[str], source_batch: str) -> Path:
    scene_paths = resolve_scene_draft_paths(sources=sources, source_batch=source_batch, count=count)
    batch_dir = build_batch_dir(BATCH_KIND, f"{label}_batch{len(scene_paths)}")
    samples_dir = batch_dir / "samples"
    ensure_dir(samples_dir)

    meta = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "count": len(scene_paths),
        "sceneDraftPaths": [str(path) for path in scene_paths],
    }
    write_json(batch_dir / "batch_meta.json", meta)

    for index, scene_path in enumerate(scene_paths, start=1):
        sample_root = samples_dir / f"{index:02d}"
        bundle = create_sample_bundle(sample_root, index)
        try:
            execute_workbench_task_in_bundle(
                PROJECT_DIR,
                bundle,
                {
                    "sourceKind": SOURCE_KIND_SCENE_DRAFT_FILE,
                    "endStage": END_STAGE_DESIGN,
                    "label": f"{BATCH_KIND}_{index:02d}",
                    "sourcePath": str(scene_path),
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
