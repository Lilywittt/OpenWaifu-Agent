from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from creative import social_trends
from io_utils import ensure_dir, normalize_spaces, unique_list, write_json
from runtime_layout import runtime_root, sanitize_segment


REQUIRED_CANDIDATE_COUNT = social_trends._SOCIAL_SIGNAL_SHORTLIST_SIZE


def social_sampling_audit_root(project_dir: Path) -> Path:
    return ensure_dir(runtime_root(project_dir) / "service_state" / "social_sampling_audits")


def _matches_filter(partition: Any, selected: set[str]) -> bool:
    if not selected:
        return True
    keys = {
        normalize_spaces(str(partition.source_key)).casefold(),
        normalize_spaces(str(partition.provider_key)).casefold(),
        normalize_spaces(str(partition.source_zh)).casefold(),
        normalize_spaces(str(partition.provider_zh)).casefold(),
    }
    return bool(keys & selected)


def _audit_partition(partition: Any, *, include_candidates: bool) -> dict[str, Any]:
    started_at = time.perf_counter()
    base = {
        "sourceKey": partition.source_key,
        "sourceZh": partition.source_zh,
        "providerKey": partition.provider_key,
        "providerZh": partition.provider_zh,
        "weight": partition.weight,
        "requiredCandidateCount": REQUIRED_CANDIDATE_COUNT,
    }
    try:
        candidates = unique_list(partition.collector())
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        candidate_count = len(candidates)
        status = "ok" if candidate_count >= REQUIRED_CANDIDATE_COUNT else "insufficient_candidates"
        result = {
            **base,
            "status": status,
            "ok": status == "ok",
            "candidateCount": candidate_count,
            "durationMs": duration_ms,
            "error": "" if status == "ok" else f"候选数量不足：{candidate_count}/{REQUIRED_CANDIDATE_COUNT}",
            "samplePreviewZh": candidates[:REQUIRED_CANDIDATE_COUNT],
        }
        if include_candidates:
            result["candidatesZh"] = candidates
        return result
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        return {
            **base,
            "status": "failed",
            "ok": False,
            "candidateCount": 0,
            "durationMs": duration_ms,
            "error": normalize_spaces(str(exc)) or exc.__class__.__name__,
            "samplePreviewZh": [],
            **({"candidatesZh": []} if include_candidates else {}),
        }


def audit_social_sampling_sources(
    project_dir: Path,
    *,
    only: list[str] | None = None,
    include_candidates: bool = True,
) -> dict[str, Any]:
    project_dir = Path(project_dir).resolve()
    selected = {normalize_spaces(item).casefold() for item in (only or []) if normalize_spaces(item)}
    registry = [
        partition
        for partition in social_trends._build_registry()
        if _matches_filter(partition, selected)
    ]
    if selected and not registry:
        raise RuntimeError("没有匹配到指定采样源。")

    checked_at = datetime.now().isoformat(timespec="seconds")
    results = [
        _audit_partition(partition, include_candidates=include_candidates)
        for partition in registry
    ]
    ok_count = sum(1 for item in results if item["ok"])
    failed = [item for item in results if not item["ok"]]
    report = {
        "meta": {
            "checkedAt": checked_at,
            "requiredCandidateCount": REQUIRED_CANDIDATE_COUNT,
            "selectedFilters": sorted(selected),
            "partitionCount": len(results),
            "okCount": ok_count,
            "failedCount": len(failed),
        },
        "results": results,
    }

    audit_root = social_sampling_audit_root(project_dir)
    report_name = f"{datetime.now().strftime('%Y%m%dT%H%M%S')}_social_sampling_audit.json"
    report_path = audit_root / sanitize_segment(report_name)
    latest_path = audit_root / "latest.json"
    write_json(report_path, report)
    write_json(latest_path, report)
    report["meta"]["reportPath"] = str(report_path)
    report["meta"]["latestReportPath"] = str(latest_path)
    write_json(report_path, report)
    write_json(latest_path, report)
    return report


def summarize_social_sampling_audit(report: dict[str, Any]) -> str:
    meta = report.get("meta", {})
    lines = [
        (
            f"[social-sampling] checked={meta.get('partitionCount', 0)} "
            f"ok={meta.get('okCount', 0)} failed={meta.get('failedCount', 0)} "
            f"required={meta.get('requiredCandidateCount', REQUIRED_CANDIDATE_COUNT)}"
        )
    ]
    for item in report.get("results", []):
        status = "OK" if item.get("ok") else "FAIL"
        line = (
            f"[{status}] {item.get('providerKey')} "
            f"count={item.get('candidateCount')}/{item.get('requiredCandidateCount')} "
            f"durationMs={item.get('durationMs')}"
        )
        error = normalize_spaces(str(item.get("error", "")))
        if error:
            line += f" error={error}"
        lines.append(line)
        preview = item.get("samplePreviewZh", [])
        if isinstance(preview, list):
            for candidate in preview:
                text = normalize_spaces(str(candidate))
                if len(text) > 220:
                    text = text[:219].rstrip() + "…"
                lines.append(f"  - {text}")
    if meta.get("reportPath"):
        lines.append(f"[social-sampling] report={meta['reportPath']}")
    return "\n".join(lines)
