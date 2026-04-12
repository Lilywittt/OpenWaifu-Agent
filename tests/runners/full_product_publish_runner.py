from __future__ import annotations

"""从采样开始运行到发布层的完整产品链路测试脚本。"""

import argparse
import json
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

from io_utils import ensure_dir, read_json, write_json, write_text
from product_pipeline import run_full_product_pipeline


BATCH_KIND = "full_product_publish"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the full product pipeline from social sampling through publish."
    )
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--label", default="batch")
    parser.add_argument("--target", action="append", default=[])
    return parser


def build_record(sample_dir: Path) -> dict[str, Any]:
    summary = read_json(sample_dir / "output" / "run_summary.json")
    publish_package = read_json(sample_dir / "publish" / "04_publish_package.json")
    return {
        "sampleId": sample_dir.name,
        "sceneDraftPremiseZh": summary.get("sceneDraftPremiseZh", ""),
        "socialPostText": summary.get("socialPostText", ""),
        "generatedImagePath": summary.get("generatedImagePath", ""),
        "publishReceipts": publish_package.get("receipts", []),
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
        "# 从采样到发布的全链路测试结果",
        "",
        f"- 批次目录: `{batch_dir}`",
        f"- 样本数: {len(records)}",
        "",
    ]
    for record in records:
        lines.append(f"## {record['sampleId']}")
        lines.append(f"- 场景命题: {record['sceneDraftPremiseZh']}")
        lines.append("### 社媒文案")
        lines.append("```text")
        lines.append(record["socialPostText"])
        lines.append("```")
        lines.append(f"- 生成图片: `{record['generatedImagePath']}`")
        lines.append("### 发布回执")
        lines.append("```json")
        lines.append(json.dumps(record["publishReceipts"], ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
    write_text(batch_dir / "complete_results.md", "\n".join(lines))
    return summary


def run_batch(*, count: int, label: str, target_ids: list[str]) -> Path:
    if count <= 0:
        raise RuntimeError("count must be greater than 0")
    batch_dir = build_batch_dir(BATCH_KIND, f"{label}_batch{count}")
    samples_dir = batch_dir / "samples"
    ensure_dir(samples_dir)
    write_json(
        batch_dir / "batch_meta.json",
        {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "count": count,
            "targetIds": target_ids,
        },
    )

    for index in range(1, count + 1):
        sample_root = samples_dir / f"{index:02d}"
        bundle = create_sample_bundle(sample_root, index)
        try:
            run_full_product_pipeline(
                PROJECT_DIR,
                bundle,
                publish_target_ids=target_ids or None,
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
        target_ids=args.target,
    )
    print(batch_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
