from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from io_utils import ensure_dir, read_json, write_json
from publish.adapters import browser_automation_adapter_names, get_publish_adapter
from publish.browser_profiles import edge_publish_sessions_root, edge_publish_target_profiles_root
from publish.package import build_publish_input
from publish.targets import load_publish_targets_config, resolve_publish_targets_for_request
from runtime_layout import runs_root, sanitize_segment


SMOKE_DIR_NAME = "smoke_jobs"
DEFAULT_RECEIPT_KEYS = (
    "status",
    "error",
    "postUrl",
    "createOpened",
    "editorReady",
    "captionReady",
    "captionFilled",
    "captionTextLength",
    "imageUploaded",
    "imagePreviewReady",
    "imagePreviewCount",
    "submitReady",
    "submitClicked",
    "submitConfirmed",
    "confirmationsClicked",
    "shareReady",
    "shareClicked",
    "loggedOut",
    "authorizationRequired",
)


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = read_json(path)
    return payload if isinstance(payload, dict) else None


def _find_latest_publishable_run(project_dir: Path) -> str:
    candidates = sorted(
        (item for item in runs_root(project_dir).glob("*") if item.is_dir()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidates:
        if _run_has_publish_inputs(candidate):
            return candidate.name
    latest_path = project_dir / "runtime" / "latest.json"
    latest_payload = _read_optional_json(latest_path)
    latest_run_id = str((latest_payload or {}).get("runId", "")).strip()
    if latest_run_id:
        candidate = runs_root(project_dir) / latest_run_id
        if _run_has_publish_inputs(candidate):
            return latest_run_id
    raise RuntimeError("没有找到可用于发布验收的 run。")


def _run_has_publish_inputs(run_dir: Path) -> bool:
    return (
        (run_dir / "creative" / "05_creative_package.json").exists()
        and (run_dir / "social_post" / "01_social_post_package.json").exists()
        and (run_dir / "execution" / "04_execution_package.json").exists()
    )


def _resolve_run_dir(project_dir: Path, run_id: str) -> Path:
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id or normalized_run_id == "latest":
        normalized_run_id = _find_latest_publishable_run(project_dir)
    run_dir = (runs_root(project_dir) / normalized_run_id).resolve()
    runs_dir = runs_root(project_dir).resolve()
    if run_dir.parent != runs_dir or not run_dir.is_dir():
        raise RuntimeError(f"未找到运行目录：{normalized_run_id}")
    if not _run_has_publish_inputs(run_dir):
        raise RuntimeError(f"运行目录缺少发布验收所需产物：{normalized_run_id}")
    return run_dir


def _build_smoke_bundle(run_dir: Path, artifacts_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        run_id=run_dir.name,
        creative_dir=run_dir / "creative",
        social_post_dir=run_dir / "social_post",
        execution_dir=run_dir / "execution",
        publish_dir=artifacts_dir,
        output_dir=artifacts_dir,
    )


def _build_publish_input(project_dir: Path, run_dir: Path, artifacts_dir: Path) -> tuple[SimpleNamespace, dict[str, Any]]:
    bundle = _build_smoke_bundle(run_dir, artifacts_dir)
    character_assets = _read_optional_json(run_dir / "input" / "character_assets_snapshot.json")
    if character_assets is None:
        character_assets = {}
    creative_package = read_json(run_dir / "creative" / "05_creative_package.json")
    social_post_package = read_json(run_dir / "social_post" / "01_social_post_package.json")
    execution_package = read_json(run_dir / "execution" / "04_execution_package.json")
    return bundle, build_publish_input(
        bundle=bundle,
        character_assets=character_assets,
        creative_package=creative_package,
        social_post_package=social_post_package,
        execution_package=execution_package,
    )


def _default_target_ids(project_dir: Path) -> list[str]:
    browser_adapters = browser_automation_adapter_names()
    targets_config = load_publish_targets_config(project_dir)
    target_ids = []
    for target_id, target_config in targets_config.get("targets", {}).items():
        if isinstance(target_config, dict) and str(target_config.get("adapter", "")).strip() in browser_adapters:
            target_ids.append(str(target_id))
    if not target_ids:
        raise RuntimeError("发布配置里没有浏览器发布目标。")
    return target_ids


def _target_session_user_data_dir(project_dir: Path, run_id: str, target: dict[str, Any], index: int) -> tuple[Path, bool]:
    target_id = str(target["targetId"])
    persistent = str(target.get("browserProfilePersistence", "")).strip().casefold() == "target"
    if persistent:
        return edge_publish_target_profiles_root(project_dir) / sanitize_segment(target_id), True
    session_id = sanitize_segment(f"smoke_{index:02d}_{run_id}_{target_id}")
    return edge_publish_sessions_root(project_dir) / session_id, False


def _smoke_target_config(
    project_dir: Path,
    run_id: str,
    target: dict[str, Any],
    *,
    index: int,
    allow_submit: bool,
) -> dict[str, Any]:
    prepared = dict(target)
    original_auto_submit = bool(prepared.get("autoSubmit", False))
    prepared["autoSubmit"] = bool(allow_submit and original_auto_submit)
    session_dir, persistent = _target_session_user_data_dir(project_dir, run_id, prepared, index)
    prepared["browserSessionUserDataDir"] = str(session_dir)
    prepared["browserSessionPersistent"] = persistent
    prepared["smokeOriginalAutoSubmit"] = original_auto_submit
    return prepared


def _receipt_preview(receipt: dict[str, Any]) -> dict[str, Any]:
    return {key: receipt[key] for key in DEFAULT_RECEIPT_KEYS if key in receipt}


def _target_passed(receipt: dict[str, Any], *, allow_submit: bool) -> bool:
    status = str(receipt.get("status", "")).strip()
    if allow_submit:
        return status == "published"
    return status in {"draft_prepared", "published"}


def run_publish_smoke(
    project_dir: Path,
    *,
    run_id: str = "latest",
    target_ids: list[str] | None = None,
    allow_submit: bool = False,
) -> dict[str, Any]:
    project_dir = Path(project_dir).resolve()
    run_dir = _resolve_run_dir(project_dir, run_id)
    selected_target_ids = list(target_ids or _default_target_ids(project_dir))
    smoke_id = datetime.now().strftime("%Y%m%dT%H%M%S")
    artifacts_dir = ensure_dir(run_dir / "publish" / SMOKE_DIR_NAME / smoke_id)
    bundle, publish_input = _build_publish_input(project_dir, run_dir, artifacts_dir)
    targets = resolve_publish_targets_for_request(
        project_dir,
        target_ids=selected_target_ids,
        publish_input=publish_input,
    )
    receipts: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for index, raw_target in enumerate(targets, start=1):
        target = _smoke_target_config(
            project_dir,
            run_dir.name,
            raw_target,
            index=index,
            allow_submit=allow_submit,
        )
        target_id = str(target["targetId"])
        adapter_name = str(target.get("adapter", "")).strip()
        request_path = artifacts_dir / f"{index:02d}_{sanitize_segment(target_id)}_request.json"
        receipt_path = artifacts_dir / f"{index:02d}_{sanitize_segment(target_id)}_receipt.json"
        request_payload = {"target": target, "publishInput": publish_input}
        write_json(request_path, request_payload)
        try:
            receipt = get_publish_adapter(adapter_name)(
                project_dir=project_dir,
                bundle=bundle,
                target_id=target_id,
                target_config=target,
                publish_input=publish_input,
            )
        except Exception as exc:
            receipt = {
                "targetId": target_id,
                "adapter": adapter_name,
                "status": "failed",
                "error": str(exc),
            }
        write_json(receipt_path, receipt)
        receipts.append(receipt)
        results.append(
            {
                "targetId": target_id,
                "adapter": adapter_name,
                "passed": _target_passed(receipt, allow_submit=allow_submit),
                "receipt": _receipt_preview(receipt),
                "requestPath": str(request_path),
                "receiptPath": str(receipt_path),
            }
        )
    passed_count = sum(1 for item in results if item["passed"])
    report = {
        "meta": {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "runId": run_dir.name,
            "allowSubmit": allow_submit,
            "targetCount": len(results),
            "passedCount": passed_count,
            "failedCount": len(results) - passed_count,
            "artifactsPath": str(artifacts_dir),
        },
        "results": results,
        "receipts": receipts,
    }
    write_json(artifacts_dir / "publish_smoke_report.json", report)
    return report


def summarize_publish_smoke(report: dict[str, Any]) -> str:
    meta = report.get("meta", {}) if isinstance(report.get("meta", {}), dict) else {}
    lines = [
        f"发布验收 run={meta.get('runId', '')} targets={meta.get('targetCount', 0)} passed={meta.get('passedCount', 0)} failed={meta.get('failedCount', 0)} allowSubmit={meta.get('allowSubmit', False)}",
        f"产物目录：{meta.get('artifactsPath', '')}",
    ]
    for item in report.get("results", []):
        if not isinstance(item, dict):
            continue
        receipt = item.get("receipt", {}) if isinstance(item.get("receipt", {}), dict) else {}
        status = receipt.get("status", "")
        error = receipt.get("error", "")
        flags = []
        for key in ("captionFilled", "captionTextLength", "imageUploaded", "imagePreviewReady", "submitReady", "shareReady", "confirmationsClicked"):
            if key in receipt:
                flags.append(f"{key}={receipt[key]}")
        line = f"- {item.get('targetId', '')}: {'PASS' if item.get('passed') else 'FAIL'} status={status}"
        if flags:
            line += " " + " ".join(flags)
        if error:
            line += f" error={error}"
        lines.append(line)
    return "\n".join(lines)
