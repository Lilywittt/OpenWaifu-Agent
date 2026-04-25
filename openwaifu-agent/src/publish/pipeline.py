from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import read_json, write_json
from publish.browser_profiles import edge_publish_sessions_root
from runtime_layout import sanitize_segment

from .adapters import get_publish_adapter
from .package import build_publish_input
from .state import append_published_record
from .targets import (
    load_publish_targets_config,
    resolve_publish_targets as resolve_publish_targets_from_config,
)


INPUT_FILENAME = "00_publish_input.json"
PLAN_FILENAME = "01_publish_plan.json"
PACKAGE_FILENAME = "04_publish_package.json"
SUMMARY_FILENAME = "publish_summary.json"
BROWSER_AUTOMATION_ADAPTERS = {
    "instagram_browser_draft",
    "pixiv_browser_draft",
}
DEFAULT_BROWSER_ADAPTER_TIMEOUT_SECONDS = 90


def _bundle_payload(bundle) -> dict[str, str]:
    return {
        "runId": str(bundle.run_id),
        "creativeDir": str(bundle.creative_dir),
        "socialPostDir": str(bundle.social_post_dir),
        "executionDir": str(bundle.execution_dir),
        "publishDir": str(bundle.publish_dir),
        "outputDir": str(bundle.output_dir),
    }


def _browser_adapter_timeout_seconds(target: dict[str, Any]) -> int:
    try:
        timeout_seconds = int(target.get("timeoutSeconds", DEFAULT_BROWSER_ADAPTER_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        timeout_seconds = DEFAULT_BROWSER_ADAPTER_TIMEOUT_SECONDS
    return max(20, min(timeout_seconds, 300))


def _browser_session_user_data_dir(project_dir: Path, bundle, target_id: str, index: int) -> Path:
    session_id = sanitize_segment(f"{Path(bundle.publish_dir).name}_{index:02d}_{bundle.run_id}_{target_id}")
    return edge_publish_sessions_root(project_dir) / session_id


def _terminate_edge_processes_for_user_data_dir(user_data_dir: Path) -> None:
    if os.name != "nt":
        return
    target = str(user_data_dir)
    escaped_target = target.replace("'", "''")
    script = (
        f"$target = '{escaped_target}'; "
        "Get-CimInstance Win32_Process -Filter \"name='msedge.exe'\" | "
        "Where-Object { $_.CommandLine -like \"*$target*\" } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


def _format_subprocess_error(result: subprocess.CompletedProcess[str]) -> str:
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part and part.strip())
    return output[-1600:] if output else f"退出码 {result.returncode}"


def _run_adapter_in_subprocess(
    *,
    project_dir: Path,
    request_path: Path,
    receipt_path: Path,
    timeout_seconds: int,
    browser_session_user_data_dir: Path,
) -> dict[str, Any]:
    env = dict(os.environ)
    src_dir = str((Path(project_dir) / "src").resolve())
    env["PYTHONPATH"] = src_dir + os.pathsep + env.get("PYTHONPATH", "")
    command = [
        sys.executable,
        "-m",
        "publish.adapter_runner",
        "--project-dir",
        str(project_dir),
        "--request",
        str(request_path),
        "--receipt",
        str(receipt_path),
    ]
    try:
        result = subprocess.run(
            command,
            cwd=project_dir,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        _terminate_edge_processes_for_user_data_dir(browser_session_user_data_dir)
        raise RuntimeError(f"浏览器发布超过 {timeout_seconds} 秒未完成，已停止本次发布会话。") from exc
    if result.returncode != 0:
        raise RuntimeError(_format_subprocess_error(result))
    if not receipt_path.exists():
        raise RuntimeError("发布适配器没有写入回执。")
    receipt = read_json(receipt_path)
    if not isinstance(receipt, dict):
        raise RuntimeError("发布适配器回执格式无效。")
    return receipt


def _raise_if_receipt_failed(target: dict[str, Any], receipt: dict[str, Any]) -> None:
    status = str(receipt.get("status", "")).strip()
    if status in {"failed", "draft_needs_attention"}:
        display_name = str(target.get("displayName", "")).strip() or str(target.get("targetId", "")).strip()
        error = str(receipt.get("error", "")).strip() or f"{display_name} 发布未完成。"
        raise RuntimeError(error)


def load_publish_targets(project_dir: Path, targets_path: Path | None = None) -> dict[str, Any]:
    return load_publish_targets_config(project_dir, targets_path)


def resolve_publish_targets(targets_config: dict[str, Any], target_ids: list[str] | None = None) -> list[dict[str, Any]]:
    return resolve_publish_targets_from_config(targets_config, target_ids)


def run_publish_stage(
    project_dir: Path,
    bundle,
    default_run_context: dict[str, Any],
    publish_input: dict[str, Any],
    *,
    targets_path: Path | None = None,
    target_ids: list[str] | None = None,
    explicit_targets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    write_json(bundle.publish_dir / INPUT_FILENAME, publish_input)

    if explicit_targets is not None:
        targets = [dict(target) for target in explicit_targets]
    else:
        targets_config = load_publish_targets(project_dir, targets_path)
        targets = resolve_publish_targets(targets_config, target_ids)
    publish_plan = {
        "meta": {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "runMode": default_run_context.get("runMode", "default"),
        },
        "defaultRunContext": default_run_context,
        "targets": targets,
    }
    write_json(bundle.publish_dir / PLAN_FILENAME, publish_plan)

    receipts: list[dict[str, Any]] = []
    for index, target in enumerate(targets, start=1):
        target_id = str(target["targetId"])
        request_filename = f"02_{index:02d}_{sanitize_segment(target_id)}_request.json"
        receipt_filename = f"03_{index:02d}_{sanitize_segment(target_id)}_receipt.json"
        request_payload = {
            "target": target,
            "publishInput": publish_input,
            "bundle": _bundle_payload(bundle),
        }
        adapter_name = str(target.get("adapter", ""))
        browser_session_user_data_dir = Path()
        if adapter_name in BROWSER_AUTOMATION_ADAPTERS:
            browser_session_user_data_dir = _browser_session_user_data_dir(project_dir, bundle, target_id, index)
            target["browserSessionUserDataDir"] = str(browser_session_user_data_dir)
            request_payload["target"] = target
        write_json(bundle.publish_dir / request_filename, request_payload)
        receipt_path = bundle.publish_dir / receipt_filename
        if adapter_name in BROWSER_AUTOMATION_ADAPTERS:
            receipt = _run_adapter_in_subprocess(
                project_dir=project_dir,
                request_path=bundle.publish_dir / request_filename,
                receipt_path=receipt_path,
                timeout_seconds=_browser_adapter_timeout_seconds(target),
                browser_session_user_data_dir=browser_session_user_data_dir,
            )
        else:
            adapter = get_publish_adapter(adapter_name)
            receipt = adapter(
                project_dir=project_dir,
                bundle=bundle,
                target_id=target_id,
                target_config=target,
                publish_input=publish_input,
            )
            write_json(receipt_path, receipt)
        receipts.append(receipt)
        _raise_if_receipt_failed(target, receipt)
        append_published_record(
            project_dir,
            {
                "runId": bundle.run_id,
                "targetId": target_id,
                "receipt": receipt,
            },
        )

    publish_package = {
        "meta": {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "runMode": default_run_context.get("runMode", "default"),
        },
        "defaultRunContext": default_run_context,
        "publishInput": publish_input,
        "receipts": receipts,
    }
    write_json(bundle.publish_dir / PACKAGE_FILENAME, publish_package)
    write_json(
        bundle.output_dir / SUMMARY_FILENAME,
        {
            "runId": bundle.run_id,
            "targetCount": len(receipts),
            "receipts": receipts,
        },
    )
    return publish_package


def run_publish_pipeline(
    project_dir: Path,
    bundle,
    default_run_context: dict[str, Any],
    character_assets: dict[str, Any],
    creative_package: dict[str, Any],
    social_post_package: dict[str, Any],
    execution_package: dict[str, Any],
    *,
    targets_path: Path | None = None,
    target_ids: list[str] | None = None,
    explicit_targets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    publish_input = build_publish_input(
        bundle=bundle,
        character_assets=character_assets,
        creative_package=creative_package,
        social_post_package=social_post_package,
        execution_package=execution_package,
    )
    return run_publish_stage(
        project_dir,
        bundle,
        default_run_context,
        publish_input,
        targets_path=targets_path,
        target_ids=target_ids,
        explicit_targets=explicit_targets,
    )
