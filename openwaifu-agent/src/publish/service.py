from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from character_assets import load_character_assets
from creative import build_default_run_context
from io_utils import normalize_spaces, read_json, write_json
from runtime_layout import runs_root

from .contracts import BROWSER_SAVE_EXECUTOR, PublishRunRequest, normalize_publish_run_request
from .jobs import build_publish_job, read_publish_job, write_publish_job
from .local_export import default_local_export_name, normalize_local_export_options
from .package import build_publish_input
from .pipeline import run_publish_stage
from .social_post_edit import (
    apply_effective_social_post_package,
    read_effective_social_post,
    save_social_post_override,
)
from .state import append_published_record
from .targets import list_publish_targets as build_publish_targets_payload
from .targets import resolve_publish_targets_for_request


def _resolve_run_dir(project_dir: Path, run_id: str) -> Path:
    normalized_run_id = normalize_spaces(run_id)
    if not normalized_run_id:
        raise RuntimeError("runId 不能为空。")
    runs_dir = runs_root(project_dir).resolve()
    run_dir = (runs_dir / normalized_run_id).resolve()
    if run_dir.parent != runs_dir or not run_dir.exists() or not run_dir.is_dir():
        raise RuntimeError(f"未找到运行目录：{normalized_run_id}")
    return run_dir


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = read_json(path)
    return payload if isinstance(payload, dict) else None


def _build_publish_bundle(run_dir: Path, publish_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        run_id=run_dir.name,
        creative_dir=run_dir / "creative",
        social_post_dir=run_dir / "social_post",
        execution_dir=run_dir / "execution",
        publish_dir=publish_dir,
        output_dir=publish_dir,
    )


def _resolve_publish_source(project_dir: Path, run_dir: Path, publish_dir: Path) -> tuple[SimpleNamespace, dict[str, Any], dict[str, Any]]:
    default_run_context = _read_optional_json(run_dir / "input" / "default_run_context.json")
    if default_run_context is None:
        default_run_context = build_default_run_context(now_local=datetime.now().isoformat(timespec="seconds"))
    character_assets = _read_optional_json(run_dir / "input" / "character_assets_snapshot.json")
    if character_assets is None:
        character_assets = load_character_assets(project_dir)
    creative_package = read_json(run_dir / "creative" / "05_creative_package.json")
    social_post_package = apply_effective_social_post_package(
        run_dir,
        read_json(run_dir / "social_post" / "01_social_post_package.json"),
    )
    execution_package = read_json(run_dir / "execution" / "04_execution_package.json")
    bundle = _build_publish_bundle(run_dir, publish_dir)
    publish_input = build_publish_input(
        bundle=bundle,
        character_assets=character_assets,
        creative_package=creative_package,
        social_post_package=social_post_package,
        execution_package=execution_package,
    )
    return bundle, default_run_context, publish_input


def _decorate_receipts(
    receipts: list[dict[str, Any]],
    *,
    job_id: str,
    artifacts_path: Path,
) -> list[dict[str, Any]]:
    return [
        {
            **dict(receipt),
            "jobId": job_id,
            "artifactsPath": str(artifacts_path),
        }
        for receipt in receipts
        if isinstance(receipt, dict)
    ]


def _update_run_summary_with_publish_receipts(run_dir: Path, *, receipts: list[dict[str, Any]], package_path: Path, job_id: str) -> None:
    summary_path = run_dir / "output" / "run_summary.json"
    summary_payload = _read_optional_json(summary_path) or {"runId": run_dir.name}
    existing_receipts = (
        summary_payload.get("publishReceipts", [])
        if isinstance(summary_payload.get("publishReceipts", []), list)
        else []
    )
    summary_payload["publishReceipts"] = receipts + existing_receipts
    summary_payload["publishPackagePath"] = str(package_path)
    summary_payload["lastPublishJobId"] = job_id
    summary_payload["lastPublishedAt"] = normalize_spaces(str(receipts[0].get("publishedAt", ""))) if receipts else ""
    write_json(summary_path, summary_payload)


def _client_publish_target(project_dir: Path, target_id: str) -> dict[str, Any]:
    normalized_target_id = normalize_spaces(target_id)
    targets_payload = build_publish_targets_payload(project_dir)
    for target in targets_payload.get("targets", []):
        if not isinstance(target, dict):
            continue
        if normalize_spaces(str(target.get("id", ""))) == normalized_target_id:
            if normalize_spaces(str(target.get("executor", ""))) != BROWSER_SAVE_EXECUTOR:
                raise RuntimeError("这个发布目标不能由浏览器回写结果。")
            return target
    raise RuntimeError(f"未知发布目标：{normalized_target_id}")


def _normalize_client_file_names(raw_value: Any) -> list[str]:
    if not isinstance(raw_value, list):
        return []
    file_names: list[str] = []
    seen: set[str] = set()
    for item in raw_value:
        file_name = normalize_spaces(str(item))
        if not file_name or "/" in file_name or "\\" in file_name or file_name in seen:
            continue
        file_names.append(file_name)
        seen.add(file_name)
    return file_names[:20]


def list_publish_targets(project_dir: Path) -> dict[str, Any]:
    return build_publish_targets_payload(project_dir)


def read_publish_social_post(project_dir: Path, run_id: str) -> dict[str, Any]:
    run_dir = _resolve_run_dir(Path(project_dir).resolve(), run_id)
    return read_effective_social_post(run_dir)


def save_publish_social_post(project_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError("发布文案请求必须是 JSON 对象。")
    run_id = normalize_spaces(str(payload.get("runId", "")))
    if not run_id:
        raise RuntimeError("runId 不能为空。")
    run_dir = _resolve_run_dir(Path(project_dir).resolve(), run_id)
    source = normalize_spaces(str(payload.get("source", ""))) or "workbench"
    return save_social_post_override(run_dir, payload.get("socialPostText", ""), source=source)


def _request_social_post_text(options: dict[str, Any]) -> Any:
    if "socialPostText" in options:
        return options["socialPostText"]
    if "caption" in options:
        return options["caption"]
    return None


def submit_publish_run(project_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    project_dir = Path(project_dir).resolve()
    request = normalize_publish_run_request(payload)
    run_dir = _resolve_run_dir(project_dir, request.run_id)
    requested_social_post_text = _request_social_post_text(request.options)
    if requested_social_post_text is not None:
        save_social_post_override(run_dir, requested_social_post_text, source="publish_request")
    job = build_publish_job(
        run_id=request.run_id,
        target_ids=list(request.target_ids),
        local_directory=request.local_directory,
    )
    artifacts_path = run_dir / "publish" / "service_jobs" / job["jobId"]
    artifacts_path.mkdir(parents=True, exist_ok=True)
    job["status"] = "running"
    job["artifactsPath"] = str(artifacts_path)
    write_publish_job(project_dir, job)
    try:
        bundle, default_run_context, publish_input = _resolve_publish_source(project_dir, run_dir, artifacts_path)
        resolved_targets = resolve_publish_targets_for_request(
            project_dir,
            target_ids=request.target_ids,
            local_directory=request.local_directory,
            options=request.options,
            publish_input=publish_input,
        )
        publish_package = run_publish_stage(
            project_dir,
            bundle,
            default_run_context,
            publish_input,
            explicit_targets=resolved_targets,
        )
        receipts = _decorate_receipts(
            publish_package.get("receipts", []) if isinstance(publish_package, dict) else [],
            job_id=job["jobId"],
            artifacts_path=artifacts_path,
        )
        publish_package["receipts"] = receipts
        write_json(artifacts_path / "04_publish_package.json", publish_package)
        _update_run_summary_with_publish_receipts(
            run_dir,
            receipts=receipts,
            package_path=artifacts_path / "04_publish_package.json",
            job_id=job["jobId"],
        )
        job["status"] = "completed"
        job["finishedAt"] = datetime.now().isoformat(timespec="seconds")
        job["receipts"] = receipts
        job["publishPackagePath"] = str(artifacts_path / "04_publish_package.json")
        write_publish_job(project_dir, job)
        return job
    except Exception as exc:
        job["status"] = "failed"
        job["finishedAt"] = datetime.now().isoformat(timespec="seconds")
        job["error"] = normalize_spaces(str(exc)) or "发布失败。"
        write_publish_job(project_dir, job)
        raise RuntimeError(job["error"]) from exc


def record_client_publish_result(project_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    project_dir = Path(project_dir).resolve()
    if not isinstance(payload, dict):
        raise RuntimeError("发布结果必须是 JSON 对象。")
    run_id = normalize_spaces(str(payload.get("runId", "")))
    target_id = normalize_spaces(str(payload.get("targetId", "")))
    if not run_id:
        raise RuntimeError("runId 不能为空。")
    if not target_id:
        raise RuntimeError("targetId 不能为空。")
    run_dir = _resolve_run_dir(project_dir, run_id)
    target = _client_publish_target(project_dir, target_id)
    published_at = datetime.now().isoformat(timespec="seconds")
    file_names = _normalize_client_file_names(payload.get("fileNames", []))
    local_export = normalize_local_export_options(
        payload.get("localExport", {}),
        default_name=default_local_export_name({"runId": run_id}),
    )
    container_name = normalize_spaces(str(payload.get("containerName", "")))
    directory_label = normalize_spaces(str(payload.get("directoryLabel", "")))
    job = build_publish_job(run_id=run_id, target_ids=[target_id])
    artifacts_path = run_dir / "publish" / "client_jobs" / job["jobId"]
    artifacts_path.mkdir(parents=True, exist_ok=True)
    receipt = {
        "targetId": target_id,
        "adapter": normalize_spaces(str(target.get("adapter", ""))) or BROWSER_SAVE_EXECUTOR,
        "status": "saved",
        "publishedAt": published_at,
        "fileCount": len(file_names),
        "fileNames": file_names,
        "localExport": local_export,
        "exportKind": local_export["kind"],
        "exportName": local_export["name"],
        "containerName": container_name,
        "directoryLabel": directory_label,
    }
    receipts = _decorate_receipts([receipt], job_id=job["jobId"], artifacts_path=artifacts_path)
    publish_package = {
        "meta": {
            "createdAt": published_at,
            "source": BROWSER_SAVE_EXECUTOR,
        },
        "clientResult": {
            "targetId": target_id,
            "fileNames": file_names,
            "localExport": local_export,
            "containerName": container_name,
            "directoryLabel": directory_label,
        },
        "receipts": receipts,
    }
    package_path = artifacts_path / "04_publish_package.json"
    write_json(package_path, publish_package)
    _update_run_summary_with_publish_receipts(
        run_dir,
        receipts=receipts,
        package_path=package_path,
        job_id=job["jobId"],
    )
    append_published_record(
        project_dir,
        {
            "runId": run_id,
            "targetId": target_id,
            "receipt": receipts[0],
        },
    )
    job["status"] = "completed"
    job["finishedAt"] = published_at
    job["artifactsPath"] = str(artifacts_path)
    job["receipts"] = receipts
    job["publishPackagePath"] = str(package_path)
    write_publish_job(project_dir, job)
    return job


def read_publish_job_status(project_dir: Path, job_id: str) -> dict[str, Any]:
    payload = read_publish_job(project_dir, job_id)
    if payload is None:
        raise RuntimeError(f"未找到发布任务：{normalize_spaces(job_id)}")
    return payload
