from __future__ import annotations

"""从采样开始运行完整 creative 链路的批量测试脚本。"""

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

from runner_common import build_batch_dir, configure_utf8_stdio, create_sample_bundle

from character_assets import load_character_assets
from creative import build_default_run_context, run_creative_pipeline
from io_utils import ensure_dir, read_json, write_json, write_text


BATCH_KIND = "creative_full_pipeline"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the full creative pipeline from sampling through the three downstream modules.")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--label", default="batch")
    return parser


def build_record(sample_dir: Path) -> dict[str, Any]:
    creative_package = read_json(sample_dir / "creative" / "05_creative_package.json")
    return {
        "sampleId": sample_dir.name,
        "socialSignalSample": creative_package.get("socialSignalSample", {}),
        "sceneDraft": creative_package.get("worldDesign", {}),
        "environmentDesign": creative_package.get("environmentDesign", ""),
        "stylingDesign": creative_package.get("stylingDesign", ""),
        "actionDesign": creative_package.get("actionDesign", ""),
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
        "# 采样起点全流程 creative 测试结果",
        "",
        f"- 批次目录: `{batch_dir}`",
        f"- 样本数: {len(records)}",
        "",
    ]
    for record in records:
        social = record["socialSignalSample"]
        lines.append(f"## {record['sampleId']}")
        lines.append(f"- 来源: {social.get('sourceZh', '')} / {social.get('providerZh', '')}")
        lines.append("- 选中采样:")
        for signal in social.get("sampledSignalsZh", []):
            lines.append(f"  - {signal}")
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
            lines.append(str(record[key]).strip())
            lines.append("```")
        lines.append("")
    write_text(batch_dir / "complete_results.md", "\n".join(lines))
    return summary


def run_batch(*, count: int, label: str) -> Path:
    if count <= 0:
        raise RuntimeError("count must be greater than 0")
    batch_dir = build_batch_dir(BATCH_KIND, f"{label}_batch{count}")
    samples_dir = batch_dir / "samples"
    ensure_dir(samples_dir)

    character_assets = load_character_assets(PROJECT_DIR)
    meta = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "count": count,
    }
    write_json(batch_dir / "batch_meta.json", meta)

    for index in range(1, count + 1):
        sample_root = samples_dir / f"{index:02d}"
        bundle = create_sample_bundle(sample_root, index)
        try:
            default_run_context = build_default_run_context(
                now_local=datetime.now().isoformat(timespec="seconds"),
            )
            write_json(bundle.input_dir / "default_run_context.json", default_run_context)
            write_json(bundle.input_dir / "character_assets_snapshot.json", character_assets)
            run_creative_pipeline(
                PROJECT_DIR,
                bundle,
                default_run_context,
                character_assets,
            )
        except Exception:
            shutil.rmtree(sample_root, ignore_errors=True)
            raise

    write_summary(batch_dir)
    return batch_dir


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    batch_dir = run_batch(count=args.count, label=args.label)
    print(batch_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
