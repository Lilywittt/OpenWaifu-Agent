from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from env import get_env_value, resolve_env_path
from io_utils import ensure_dir, write_json
from path_policy import resolve_workspace_local_root
from process_utils import (
    build_windows_background_popen_kwargs,
    find_tcp_listening_pid,
    is_process_alive,
    resolve_background_python_executable,
    terminate_process_tree,
)


def _workspace_root(project_dir: Path) -> Path:
    return resolve_workspace_local_root(project_dir).parent


def _default_comfyui_install_root(project_dir: Path) -> Path:
    return resolve_workspace_local_root(project_dir) / "ComfyUI"


def _default_comfyui_venv_dir(project_dir: Path) -> Path:
    return resolve_workspace_local_root(project_dir) / "comfyui-env"


def _should_bypass_proxy(url: str) -> bool:
    host = (urlparse(url).hostname or "").strip().casefold()
    return host in {"127.0.0.1", "localhost", "::1"}


def _open_request(request: Request, *, timeout_ms: int):
    timeout_seconds = timeout_ms / 1000
    if _should_bypass_proxy(request.full_url):
        opener = build_opener(ProxyHandler({}))
        return opener.open(request, timeout=timeout_seconds)
    return urlopen(request, timeout=timeout_seconds)


def _request_json(url: str, *, timeout_ms: int, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    with _open_request(request, timeout_ms=timeout_ms) as response:
        return json.loads(response.read().decode("utf-8"))


def is_endpoint_ready(endpoint: str, health_path: str, *, timeout_ms: int = 5000) -> bool:
    try:
        _request_json(endpoint.rstrip("/") + health_path, timeout_ms=timeout_ms)
        return True
    except Exception:
        return False


def _start_local_comfyui(project_dir: Path, endpoint: str) -> int:
    install_root = resolve_env_path(project_dir, "COMFYUI_INSTALL_ROOT", str(_default_comfyui_install_root(project_dir)))
    venv_dir = resolve_env_path(project_dir, "COMFYUI_VENV_DIR", str(_default_comfyui_venv_dir(project_dir)))
    python_path = venv_dir / "Scripts" / "python.exe"
    main_py = install_root / "main.py"
    if not python_path.exists():
        raise RuntimeError(f"ComfyUI python not found: {python_path}")
    if not main_py.exists():
        raise RuntimeError(f"ComfyUI main.py not found: {main_py}")
    launch_python_path = resolve_background_python_executable(python_path)

    parsed = urlparse(endpoint)
    host = parsed.hostname or "127.0.0.1"
    port = int(parsed.port or 8188)
    listener_pid = find_tcp_listening_pid(port)
    if listener_pid > 0 and is_process_alive(listener_pid):
        raise RuntimeError(
            f"ComfyUI endpoint is not healthy at {endpoint}, but TCP port {port} is already occupied by pid {listener_pid}. "
            "Stop that process before starting a new ComfyUI instance."
        )

    log_dir = resolve_env_path(project_dir, "COMFYUI_LOG_DIR", "./runtime/service_logs/comfyui")
    pid_dir = resolve_env_path(project_dir, "COMFYUI_PID_DIR", "./runtime/service_state")
    ensure_dir(log_dir)
    ensure_dir(pid_dir)
    stdout_path = log_dir / "comfyui.stdout.log"
    stderr_path = log_dir / "comfyui.stderr.log"

    stdout_handle = stdout_path.open("ab")
    stderr_handle = stderr_path.open("ab")
    try:
        process = subprocess.Popen(
            [str(launch_python_path), str(main_py), "--listen", host, "--port", str(port)],
            cwd=str(install_root),
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            close_fds=True,
            **build_windows_background_popen_kwargs(),
        )
    finally:
        stdout_handle.close()
        stderr_handle.close()

    write_json(
        pid_dir / "comfyui.pid.json",
        {
            "pid": process.pid,
            "endpoint": endpoint,
            "startedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "installRoot": str(install_root),
            "pythonPath": str(launch_python_path),
        },
    )
    return int(process.pid)


def ensure_comfyui_ready(project_dir: Path, endpoint: str, health_path: str, *, start_timeout_ms: int = 180000) -> None:
    if is_endpoint_ready(endpoint, health_path):
        return
    started_pid = _start_local_comfyui(project_dir, endpoint)
    deadline = time.time() + start_timeout_ms / 1000
    while time.time() < deadline:
        if is_endpoint_ready(endpoint, health_path):
            return
        time.sleep(3)
    if started_pid > 0 and is_process_alive(started_pid):
        terminate_process_tree(started_pid)
    raise RuntimeError(f"ComfyUI did not become ready at {endpoint} within {start_timeout_ms} ms.")


def submit_workflow(endpoint: str, submit_path: str, request_body: dict[str, Any], *, timeout_ms: int) -> dict[str, Any]:
    try:
        return _request_json(endpoint.rstrip("/") + submit_path, timeout_ms=timeout_ms, method="POST", payload=request_body)
    except HTTPError as error:
        raise RuntimeError(f"ComfyUI submit failed with HTTP {error.code}: {error.read().decode('utf-8', errors='replace')}") from error
    except URLError as error:
        raise RuntimeError(f"ComfyUI submit transport error: {error}") from error


def wait_for_prompt_completion(
    endpoint: str,
    history_path_template: str,
    prompt_id: str,
    *,
    poll_interval_ms: int,
    poll_timeout_ms: int,
    should_abort=None,
) -> dict[str, Any]:
    history_url = endpoint.rstrip("/") + history_path_template.format(prompt_id=prompt_id)
    deadline = time.time() + poll_timeout_ms / 1000
    while time.time() < deadline:
        if should_abort is not None and should_abort():
            raise InterruptedError("Generation interrupted by command.")
        payload = _request_json(history_url, timeout_ms=max(poll_interval_ms, 5000))
        if isinstance(payload, dict) and prompt_id in payload:
            prompt_payload = payload[prompt_id]
            outputs = prompt_payload.get("outputs", {})
            if outputs:
                return prompt_payload
        elif isinstance(payload, dict) and payload.get("outputs"):
            return payload
        time.sleep(poll_interval_ms / 1000)
    raise RuntimeError(f"ComfyUI prompt {prompt_id} did not finish within {poll_timeout_ms} ms.")


def extract_first_output_image(history_payload: dict[str, Any], preferred_node_ids: list[str]) -> dict[str, Any]:
    outputs = history_payload.get("outputs", {})
    for node_id in [str(item) for item in preferred_node_ids]:
        node_output = outputs.get(node_id, {})
        images = node_output.get("images", [])
        if images:
            return images[0]
    for node_output in outputs.values():
        images = node_output.get("images", [])
        if images:
            return images[0]
    raise RuntimeError("ComfyUI history payload did not contain any output images.")


def download_image(endpoint: str, view_path: str, image_payload: dict[str, Any], destination_path: Path, *, timeout_ms: int) -> None:
    query = urlencode(
        {
            "filename": image_payload.get("filename", ""),
            "subfolder": image_payload.get("subfolder", ""),
            "type": image_payload.get("type", "output"),
        }
    )
    request = Request(endpoint.rstrip("/") + view_path + "?" + query, method="GET")
    try:
        with _open_request(request, timeout_ms=timeout_ms) as response:
            binary = response.read()
    except HTTPError as error:
        raise RuntimeError(f"ComfyUI image download failed with HTTP {error.code}: {error.read().decode('utf-8', errors='replace')}") from error
    except URLError as error:
        raise RuntimeError(f"ComfyUI image download transport error: {error}") from error

    ensure_dir(destination_path.parent)
    destination_path.write_bytes(binary)
