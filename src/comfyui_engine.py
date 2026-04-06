from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from env import get_env_value, resolve_env_path
from io_utils import read_json, write_json


def _http_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 120) -> Any:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def ensure_comfyui_ready(endpoint: str) -> None:
    try:
        with urlopen(f"{endpoint.rstrip('/')}/system_stats", timeout=15) as response:
            if response.status != 200:
                raise RuntimeError(f"ComfyUI health check failed with HTTP {response.status}")
    except URLError as error:
        raise RuntimeError(f"ComfyUI endpoint is not reachable: {endpoint}") from error


def resolve_comfyui_settings(project_dir: Path, endpoint_override: str = "") -> dict[str, Path | str]:
    endpoint = endpoint_override.strip() or get_env_value(project_dir, "COMFYUI_ENDPOINT", "http://127.0.0.1:8188")
    install_root = resolve_env_path(project_dir, "COMFYUI_INSTALL_ROOT")
    venv_dir = resolve_env_path(project_dir, "COMFYUI_VENV_DIR")
    log_dir = resolve_env_path(project_dir, "COMFYUI_LOG_DIR", "./runtime/service_logs/comfyui")
    pid_dir = resolve_env_path(project_dir, "COMFYUI_PID_DIR", "./runtime/service_state")
    return {
        "endpoint": endpoint,
        "install_root": install_root,
        "venv_dir": venv_dir,
        "log_dir": log_dir,
        "pid_dir": pid_dir,
    }


def start_local_comfyui(project_dir: Path, endpoint: str) -> None:
    settings = resolve_comfyui_settings(project_dir, endpoint)
    install_root = Path(settings["install_root"])
    venv_dir = Path(settings["venv_dir"])
    if not install_root or not venv_dir:
        raise RuntimeError("COMFYUI_INSTALL_ROOT and COMFYUI_VENV_DIR must be set in the project .env.")
    python_path = venv_dir / "Scripts" / "python.exe"
    main_py_path = install_root / "main.py"
    if not main_py_path.exists() or not python_path.exists():
        raise RuntimeError("The ComfyUI install path or venv path in the project .env does not exist.")
    log_dir = Path(settings["log_dir"])
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / "comfyui.stdout.log"
    stderr_path = log_dir / "comfyui.stderr.log"
    creationflags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags |= subprocess.CREATE_NO_WINDOW
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP
    stdout_handle = open(stdout_path, "ab")
    stderr_handle = open(stderr_path, "ab")
    process = subprocess.Popen(
        [str(python_path), str(main_py_path), "--listen", "127.0.0.1", "--port", "8188"],
        cwd=install_root,
        stdout=stdout_handle,
        stderr=stderr_handle,
        creationflags=creationflags,
        close_fds=False,
    )
    pid_dir = Path(settings["pid_dir"])
    pid_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        pid_dir / "comfyui.pid.json",
        {
            "pid": process.pid,
            "endpoint": endpoint,
            "installRoot": str(install_root),
            "stdoutPath": str(stdout_path),
            "stderrPath": str(stderr_path),
        },
    )
    deadline = time.time() + 180
    last_error = None
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"ComfyUI exited early with code {process.returncode}.")
        try:
            ensure_comfyui_ready(endpoint)
            return
        except Exception as error:  # noqa: BLE001
            last_error = error
            time.sleep(3)
    raise RuntimeError(f"ComfyUI did not become healthy in time: {last_error}")


def build_workflow_request(project_dir: Path, bundle, render_packet: dict[str, Any], prompt_bundle: dict[str, Any], provider_name: str, endpoint: str) -> dict[str, Any]:
    provider_catalog = read_json(project_dir / "config" / "provider_catalog.json")
    provider_spec = provider_catalog[provider_name]
    profile = read_json(project_dir / "config" / "render" / "comfyui_anime_engineering_profile.json")
    workflow = read_json(project_dir / "config" / "workflows" / "comfyui" / "anime_engineering_api.workflow.json")
    resolved_endpoint = resolve_comfyui_settings(project_dir, endpoint)["endpoint"]
    aspect_ratio = render_packet["aspectRatio"]
    size = profile["sizeByAspectRatio"][aspect_ratio]

    workflow[profile["nodes"]["checkpoint"]["id"]]["inputs"][profile["nodes"]["checkpoint"]["input"]] = provider_spec["defaultModel"]
    workflow[profile["nodes"]["positivePrompt"]["id"]]["inputs"][profile["nodes"]["positivePrompt"]["input"]] = prompt_bundle["positivePrompt"]
    workflow[profile["nodes"]["negativePrompt"]["id"]]["inputs"][profile["nodes"]["negativePrompt"]["input"]] = prompt_bundle["negativePrompt"]
    workflow[profile["nodes"]["latentImage"]["id"]]["inputs"][profile["nodes"]["latentImage"]["widthInput"]] = size["width"]
    workflow[profile["nodes"]["latentImage"]["id"]]["inputs"][profile["nodes"]["latentImage"]["heightInput"]] = size["height"]
    workflow[profile["nodes"]["latentImage"]["id"]]["inputs"][profile["nodes"]["latentImage"]["batchInput"]] = 1
    workflow[profile["nodes"]["sampler"]["id"]]["inputs"][profile["nodes"]["sampler"]["seedInput"]] = render_packet["workflow"]["seed"]
    workflow[profile["nodes"]["sampler"]["id"]]["inputs"][profile["nodes"]["sampler"]["stepsInput"]] = profile["defaults"]["steps"]
    workflow[profile["nodes"]["sampler"]["id"]]["inputs"][profile["nodes"]["sampler"]["cfgInput"]] = profile["defaults"]["cfg"]
    workflow[profile["nodes"]["sampler"]["id"]]["inputs"][profile["nodes"]["sampler"]["samplerInput"]] = profile["defaults"]["samplerName"]
    workflow[profile["nodes"]["sampler"]["id"]]["inputs"][profile["nodes"]["sampler"]["schedulerInput"]] = profile["defaults"]["scheduler"]
    workflow[profile["nodes"]["sampler"]["id"]]["inputs"][profile["nodes"]["sampler"]["denoiseInput"]] = profile["defaults"]["denoise"]
    workflow[profile["nodes"]["saveImage"]["id"]]["inputs"][profile["nodes"]["saveImage"]["input"]] = bundle.run_id

    payload = {"prompt": workflow}
    write_json(bundle.render_dir / "workflow_request.json", payload)
    write_json(bundle.render_dir / "workflow_profile_snapshot.json", profile)
    return {
        "provider": provider_name,
        "endpoint": resolved_endpoint,
        "submitPayload": payload,
        "profile": profile,
    }


def _find_output_item(history_payload: dict[str, Any], preferred_node_ids: list[str]) -> dict[str, Any]:
    for prompt_payload in history_payload.values():
        outputs = prompt_payload.get("outputs", {})
        for node_id in preferred_node_ids:
            images = (outputs.get(node_id) or {}).get("images") or []
            if images:
                return images[0]
    raise RuntimeError("ComfyUI history did not contain an output image.")


def run_generation(project_dir: Path, bundle, workflow_bundle: dict[str, Any], endpoint: str, auto_start: bool = True) -> dict[str, Any]:
    resolved_endpoint = resolve_comfyui_settings(project_dir, endpoint)["endpoint"]
    try:
        ensure_comfyui_ready(resolved_endpoint)
    except Exception:
        if not auto_start:
            raise
        start_local_comfyui(project_dir, resolved_endpoint)

    submit_url = resolved_endpoint.rstrip("/") + "/prompt"
    history_url_template = resolved_endpoint.rstrip("/") + "/history/{prompt_id}"
    view_url = resolved_endpoint.rstrip("/") + "/view"
    submit_response = _http_json("POST", submit_url, workflow_bundle["submitPayload"], timeout=120)
    write_json(bundle.trace_dir / "comfyui_submit_response.json", submit_response)
    prompt_id = str(submit_response.get("prompt_id") or "")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI did not return prompt_id: {submit_response}")

    preferred_node_ids = workflow_bundle["profile"]["nodes"]["output"]["preferredNodeIds"]
    deadline = time.time() + 900
    history_payload = {}
    while time.time() < deadline:
        history_payload = _http_json("GET", history_url_template.format(prompt_id=prompt_id), timeout=120)
        if history_payload:
            try:
                item = _find_output_item(history_payload, preferred_node_ids)
                write_json(bundle.trace_dir / "comfyui_history.json", history_payload)
                query = urlencode(
                    {
                        "filename": item["filename"],
                        "subfolder": item.get("subfolder", ""),
                        "type": item.get("type", "output"),
                    }
                )
                with urlopen(f"{view_url}?{query}", timeout=120) as response:
                    image_bytes = response.read()
                extension = Path(item["filename"]).suffix or ".png"
                output_path = bundle.output_dir / f"final_image{extension}"
                output_path.write_bytes(image_bytes)
                result = {
                    "status": "image_generated_local_only",
                    "promptId": prompt_id,
                    "imagePath": str(output_path),
                    "outputItem": item,
                }
                write_json(bundle.output_dir / "generation_result.json", result)
                return result
            except RuntimeError:
                pass
        time.sleep(5)
    raise RuntimeError("ComfyUI generation timed out.")
