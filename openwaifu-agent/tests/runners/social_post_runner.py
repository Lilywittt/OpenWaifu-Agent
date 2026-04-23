from __future__ import annotations

"""从已有 creative 产物直接回放社媒文案模块的测试脚本。"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
TOOLS_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
for import_path in (TOOLS_DIR, SRC_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from runner_common import (
    build_batch_dir,
    configure_utf8_stdio,
    latest_creative_package_paths,
    create_sample_bundle,
    resolve_creative_package_paths,
)

from io_utils import ensure_dir, read_json, write_json, write_text
from test_pipeline import (
    END_STAGE_SOCIAL_POST,
    SOURCE_KIND_CREATIVE_PACKAGE_FILE,
    execute_workbench_task_in_bundle,
)


BATCH_KIND = "social_post_from_creative"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the social_post module directly from existing creative outputs."
    )
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--label", default="batch")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--source-batch", default="")
    return parser


def resolve_input_creative_packages(*, sources: list[str], source_batch: str, count: int) -> list[Path]:
    if sources or source_batch:
        return resolve_creative_package_paths(sources=sources, source_batch=source_batch, count=count)
    return latest_creative_package_paths(count)


def build_record(sample_dir: Path) -> dict:
    source_meta_path = sample_dir / "input" / "content_workbench_source.json"
    if not source_meta_path.exists():
        source_meta_path = sample_dir / "input" / "creative_source.json"
    source_meta = read_json(source_meta_path)
    scene_draft = read_json(sample_dir / "creative" / "01_world_design.json")
    social_post_package = read_json(sample_dir / "social_post" / "01_social_post_package.json")
    return {
        "sampleId": sample_dir.name,
        "source": source_meta,
        "sceneDraft": scene_draft,
        "socialPostText": str(social_post_package.get("socialPostText", "")).strip(),
        "socialPostOutputPath": str(sample_dir / "output" / "social_post.txt"),
    }


def write_summary(batch_dir: Path) -> dict:
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
        "# 已有设计稿直跑社媒文案测试结果",
        "",
        f"- 批次目录: `{batch_dir}`",
        f"- 样本数: {len(records)}",
        "",
    ]
    for record in records:
        lines.append(f"## {record['sampleId']}")
        lines.append(f"- 来源 creative package: `{record['source'].get('sourcePath', record['source'].get('creativePackagePath', ''))}`")
        lines.append(f"- 场景命题: {record['sceneDraft'].get('scenePremiseZh', '')}")
        lines.append("### 场景正文")
        lines.append("```text")
        lines.append(str(record["sceneDraft"].get("worldSceneZh", "")).strip())
        lines.append("```")
        lines.append("### 社媒文案")
        lines.append("```text")
        lines.append(record["socialPostText"])
        lines.append("```")
        lines.append(f"- 文案输出: `{record['socialPostOutputPath']}`")
        lines.append("")
    write_text(batch_dir / "complete_results.md", "\n".join(lines))
    return summary


def run_batch(*, count: int, label: str, sources: list[str], source_batch: str) -> Path:
    creative_package_paths = resolve_input_creative_packages(
        sources=sources,
        source_batch=source_batch,
        count=count,
    )
    batch_dir = build_batch_dir(BATCH_KIND, f"{label}_batch{len(creative_package_paths)}")
    samples_dir = batch_dir / "samples"
    ensure_dir(samples_dir)

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
            execute_workbench_task_in_bundle(
                PROJECT_DIR,
                bundle,
                {
                    "sourceKind": SOURCE_KIND_CREATIVE_PACKAGE_FILE,
                    "endStage": END_STAGE_SOCIAL_POST,
                    "label": f"{BATCH_KIND}_{index:02d}",
                    "sourcePath": str(creative_package_path),
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
