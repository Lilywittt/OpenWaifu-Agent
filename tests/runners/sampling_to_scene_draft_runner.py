from __future__ import annotations

"""从采样到场景设计稿的 world_design 批量测试脚本。"""

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[2]
TOOLS_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
for import_path in (TOOLS_DIR, SRC_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from character_assets import load_character_assets
from creative.pipeline import run_social_signal_filter_stage, run_world_design_stage
from io_utils import ensure_dir, read_json, write_json, write_text
from runner_common import build_batch_dir, configure_utf8_stdio, create_sample_bundle


BATCH_KIND = "sampling_to_scene_draft"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="world_design 批量测试工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="运行 world_design 批量测试")
    run_parser.add_argument("--count", type=int, default=30)
    run_parser.add_argument("--label", default="batch")
    run_parser.add_argument("--source-key", default="")
    run_parser.add_argument("--provider-key", default="")

    summarize_parser = subparsers.add_parser("summarize", help="重建批次汇总")
    summarize_parser.add_argument("batch_dir")

    clean_parser = subparsers.add_parser("clean", help="删除一个批次目录")
    clean_parser.add_argument("batch_dir")
    return parser


def patch_world_input(
    sample_root: Path,
    *,
    source_key: str,
    provider_key: str,
) -> None:
    if not source_key and not provider_key:
        return
    input_path = sample_root / "creative" / "01_world_design_input.json"
    if not input_path.exists():
        return
    payload = read_json(input_path)
    social = payload.get("socialSignalSample", {})
    if source_key and social.get("sourceKey") != source_key:
        raise RuntimeError(f"source_key mismatch: expected {source_key}, got {social.get('sourceKey')}")
    if provider_key and social.get("providerKey") != provider_key:
        raise RuntimeError(f"provider_key mismatch: expected {provider_key}, got {social.get('providerKey')}")


def collect_sample_record(sample_dir: Path) -> dict[str, Any] | None:
    input_path = sample_dir / "creative" / "01_world_design_input.json"
    output_path = sample_dir / "creative" / "01_world_design.json"
    if not input_path.exists() or not output_path.exists():
        return None
    world_input = read_json(input_path)
    world_output = read_json(output_path)
    social = world_input.get("socialSignalSample", {})
    return {
        "sampleId": sample_dir.name,
        "sourceKey": social.get("sourceKey", ""),
        "sourceZh": social.get("sourceZh", ""),
        "providerKey": social.get("providerKey", ""),
        "providerZh": social.get("providerZh", ""),
        "sampledSignalsZh": social.get("sampledSignalsZh", []),
        "scenePremiseZh": world_output.get("scenePremiseZh", ""),
        "worldSceneZh": world_output.get("worldSceneZh", ""),
    }


def build_keyword_analysis(samples: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = {
        "after_school": ["放学后"],
        "campus_adjacent": ["校服", "社团", "书包", "便利店", "放学后"],
        "art_lit_spaces": ["书店", "画室", "暗房", "电影院", "文具店", "电话亭", "旧物市集", "报亭", "图书馆"],
        "light_fantasy": ["幽灵", "时空", "魔法", "命运", "无限", "数字幽灵"],
        "dusk": ["黄昏", "傍晚", "暮色"],
    }
    result: dict[str, Any] = {}
    for bucket, keywords in buckets.items():
        matched = []
        for sample in samples:
            text = sample["scenePremiseZh"] + "\n" + sample["worldSceneZh"]
            if any(keyword in text for keyword in keywords):
                matched.append(sample["sampleId"])
        result[bucket] = matched
    return result


def summarize_batch(batch_dir: Path) -> dict[str, Any]:
    samples_dir = batch_dir / "samples"
    records = []
    for sample_dir in sorted([path for path in samples_dir.iterdir() if path.is_dir()], key=lambda path: path.name):
        record = collect_sample_record(sample_dir)
        if record is not None:
            records.append(record)

    source_counts = Counter(record["sourceZh"] for record in records)
    provider_counts = Counter(record["providerZh"] for record in records)
    premise_counts = Counter(record["scenePremiseZh"] for record in records)
    duplicate_premises = {key: value for key, value in premise_counts.items() if value > 1}
    keyword_analysis = build_keyword_analysis(records)

    summary = {
        "batchDir": str(batch_dir),
        "sampleCount": len(records),
        "sourceCounts": dict(source_counts),
        "providerCounts": dict(provider_counts),
        "duplicatePremises": duplicate_premises,
        "keywordAnalysis": keyword_analysis,
        "samples": records,
    }
    write_json(batch_dir / "batch_summary.json", summary)

    lines: list[str] = []
    lines.append("# world_design 批量测试完整结果")
    lines.append("")
    lines.append(f"- 批次目录: `{batch_dir}`")
    lines.append(f"- 样本数: {len(records)}")
    lines.append("")
    lines.append("## 来源统计")
    for key, value in sorted(source_counts.items()):
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## 分区统计")
    for key, value in sorted(provider_counts.items()):
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## 语义复现粗统计")
    for key, matched in keyword_analysis.items():
        lines.append(f"- {key}: {len(matched)} -> {', '.join(matched) if matched else '无'}")
    lines.append("")

    for record in records:
        lines.append(f"## {record['sampleId']}")
        lines.append(f"- 来源: {record['sourceZh']} / {record['providerZh']}")
        lines.append(f"- 场景命题: {record['scenePremiseZh']}")
        lines.append("- 采样内容:")
        for signal in record["sampledSignalsZh"]:
            lines.append(f"  - {signal}")
        lines.append("- 场景正文:")
        lines.append("```text")
        lines.append(record["worldSceneZh"])
        lines.append("```")
        lines.append("")

    write_text(batch_dir / "complete_results.md", "\n".join(lines))
    return summary


def run_batch(*, count: int, label: str, source_key: str, provider_key: str) -> Path:
    batch_dir = build_batch_dir(BATCH_KIND, f"{label}_batch{count}")
    samples_dir = batch_dir / "samples"
    ensure_dir(samples_dir)

    character_assets = load_character_assets(PROJECT_DIR)
    meta = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "count": count,
        "sourceKey": source_key,
        "providerKey": provider_key,
    }
    write_json(batch_dir / "batch_meta.json", meta)

    completed = 0
    for index in range(1, count + 1):
        sample_root = samples_dir / f"{index:02d}"
        bundle = create_sample_bundle(sample_root, index)
        try:
            social_signal_sample = run_social_signal_filter_stage(PROJECT_DIR, bundle)
            run_world_design_stage(PROJECT_DIR, bundle, character_assets["subjectProfile"], social_signal_sample)
            patch_world_input(sample_root, source_key=source_key, provider_key=provider_key)
            completed += 1
        except Exception:
            shutil.rmtree(sample_root, ignore_errors=True)
            raise

    summary = summarize_batch(batch_dir)
    meta["completed"] = completed
    meta["sampleCount"] = summary["sampleCount"]
    write_json(batch_dir / "batch_meta.json", meta)
    return batch_dir


def clean_batch(batch_dir: Path) -> None:
    if batch_dir.exists():
        shutil.rmtree(batch_dir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    if args.command == "run":
        batch_dir = run_batch(
            count=args.count,
            label=args.label,
            source_key=args.source_key,
            provider_key=args.provider_key,
        )
        print(batch_dir)
        return 0
    if args.command == "summarize":
        batch_dir = Path(args.batch_dir).resolve()
        summary = summarize_batch(batch_dir)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.command == "clean":
        clean_batch(Path(args.batch_dir).resolve())
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
