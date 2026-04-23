from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from env import get_env_value
from io_utils import write_json

from .comfyui_client import (
    download_image,
    ensure_comfyui_ready,
    extract_first_output_image,
    submit_workflow,
    wait_for_prompt_completion,
)
from .workflow import (
    build_execution_input,
    build_workflow_request,
    load_execution_profile,
    resolve_active_execution_profile_path,
    resolve_checkpoint_name,
    resolve_checkpoint_path,
)


def _resolve_endpoint(project_dir: Path, profile: dict[str, Any]) -> str:
    env_name = str(profile.get("endpointEnvName", "COMFYUI_ENDPOINT"))
    return get_env_value(project_dir, env_name, "http://127.0.0.1:8188").strip() or "http://127.0.0.1:8188"


def run_execution_pipeline(
    project_dir: Path,
    bundle,
    default_run_context: dict[str, Any],
    prompt_package: dict[str, Any],
    profile_path: Path | None = None,
    should_abort=None,
) -> dict[str, Any]:
    if should_abort is not None and should_abort():
        raise InterruptedError("Generation interrupted by command.")
    resolved_profile_path = profile_path or resolve_active_execution_profile_path(project_dir)
    profile, workflow_template, template_path = load_execution_profile(project_dir, resolved_profile_path)
    checkpoint_path = resolve_checkpoint_path(project_dir, profile)
    if not checkpoint_path.exists():
        raise RuntimeError(f"Configured checkpoint path does not exist: {checkpoint_path}")

    execution_input = build_execution_input(profile, prompt_package)
    execution_input["checkpointName"] = resolve_checkpoint_name(project_dir, profile)
    if not execution_input["checkpointName"]:
        raise RuntimeError("Configured checkpoint name is empty.")
    execution_input["checkpointPath"] = str(checkpoint_path)
    execution_input["endpoint"] = _resolve_endpoint(project_dir, profile)
    write_json(bundle.execution_dir / "00_execution_input.json", execution_input)

    request_config = profile["request"]
    ensure_comfyui_ready(
        project_dir,
        execution_input["endpoint"],
        str(request_config["healthPath"]),
        start_timeout_ms=int(request_config.get("startTimeoutMs", 180000)),
    )

    workflow_prompt = build_workflow_request(profile, workflow_template, execution_input, run_id=bundle.run_id)
    request_body = {
        "prompt": workflow_prompt,
        "client_id": f"ig_roleplay_v3_{bundle.run_id}",
    }
    write_json(bundle.execution_dir / "01_workflow_request.json", request_body)

    submit_response = submit_workflow(
        execution_input["endpoint"],
        str(request_config["submitPath"]),
        request_body,
        timeout_ms=int(request_config["submitTimeoutMs"]),
    )
    write_json(bundle.execution_dir / "02_submit_response.json", submit_response)

    prompt_id = str(submit_response.get("prompt_id", "")).strip()
    if not prompt_id:
        raise RuntimeError("ComfyUI submit response did not contain prompt_id.")
    if should_abort is not None and should_abort():
        raise InterruptedError("Generation interrupted by command.")

    history_payload = wait_for_prompt_completion(
        execution_input["endpoint"],
        str(request_config["historyPath"]),
        prompt_id,
        poll_interval_ms=int(request_config["pollIntervalMs"]),
        poll_timeout_ms=int(request_config["pollTimeoutMs"]),
        should_abort=should_abort,
    )
    write_json(bundle.execution_dir / "03_workflow_history.json", history_payload)

    image_payload = extract_first_output_image(history_payload, list(profile["nodes"]["output"]["preferredNodeIds"]))
    extension = Path(str(image_payload.get("filename", "generated.png"))).suffix or ".png"
    image_output_path = bundle.output_dir / f"{execution_input['filenamePrefix']}_{bundle.run_id}{extension}"
    if should_abort is not None and should_abort():
        raise InterruptedError("Generation interrupted by command.")
    download_image(
        execution_input["endpoint"],
        str(request_config["viewPath"]),
        image_payload,
        image_output_path,
        timeout_ms=int(request_config["downloadTimeoutMs"]),
    )

    execution_package = {
        "meta": {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "runMode": default_run_context.get("runMode", "default"),
        },
        "defaultRunContext": default_run_context,
        "profileId": profile["profileId"],
        "templatePath": str(template_path),
        "endpoint": execution_input["endpoint"],
        "checkpointName": execution_input["checkpointName"],
        "checkpointPath": execution_input["checkpointPath"],
        "promptId": prompt_id,
        "positivePrompt": execution_input["positivePrompt"],
        "negativePrompt": execution_input["negativePrompt"],
        "width": execution_input["width"],
        "height": execution_input["height"],
        "seed": execution_input["seed"],
        "imagePath": str(image_output_path),
    }
    write_json(bundle.execution_dir / "04_execution_package.json", execution_package)
    return execution_package
