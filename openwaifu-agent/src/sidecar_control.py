from __future__ import annotations

import json
import shutil
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from io_utils import ensure_dir, write_json
from process_utils import (
    find_tcp_listening_pid,
    is_process_alive,
    spawn_background_process,
    terminate_process,
)
from runtime_layout import runtime_root


HealthFetcher = Callable[[str], dict[str, Any] | None]


@dataclass(frozen=True)
class HttpSidecarSpec:
    sidecar_id: str
    label: str
    project_dir: Path
    browser_url: str
    port: int
    stdout_log_path: Path
    stderr_log_path: Path
    fetch_health: HealthFetcher


def sidecar_runtime_state_root(project_dir: Path) -> Path:
    return ensure_dir(runtime_root(project_dir) / "service_state" / "sidecars")


def legacy_sidecar_state_root(project_dir: Path, sidecar_id: str) -> Path:
    return runtime_root(project_dir) / "service_state" / "ops" / str(sidecar_id).strip()


def sidecar_logs_root(project_dir: Path, sidecar_id: str) -> Path:
    return ensure_dir(runtime_root(project_dir) / "service_logs" / "sidecars" / str(sidecar_id).strip())


def _migrate_legacy_sidecar_state(project_dir: Path, sidecar_id: str) -> None:
    legacy_root = legacy_sidecar_state_root(project_dir, sidecar_id)
    if not legacy_root.exists() or not legacy_root.is_dir():
        return

    current_root = sidecar_runtime_state_root(project_dir) / str(sidecar_id).strip()
    if current_root.exists():
        shutil.rmtree(legacy_root, ignore_errors=True)
        return

    ensure_dir(current_root.parent)
    shutil.copytree(legacy_root, current_root)
    shutil.rmtree(legacy_root, ignore_errors=True)


def sidecar_state_root(project_dir: Path, sidecar_id: str) -> Path:
    normalized_sidecar_id = str(sidecar_id).strip()
    _migrate_legacy_sidecar_state(project_dir, normalized_sidecar_id)
    return ensure_dir(sidecar_runtime_state_root(project_dir) / normalized_sidecar_id)


def sidecar_server_process_path(project_dir: Path, sidecar_id: str) -> Path:
    return sidecar_state_root(project_dir, sidecar_id) / "server_process.json"


def read_sidecar_server_process(project_dir: Path, sidecar_id: str) -> dict[str, Any] | None:
    path = sidecar_server_process_path(project_dir, sidecar_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def write_sidecar_server_process(project_dir: Path, sidecar_id: str, payload: dict[str, Any]) -> Path:
    path = sidecar_server_process_path(project_dir, sidecar_id)
    write_json(
        path,
        {
            **payload,
            "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
    )
    return path


def _normalized_sidecar_process_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    try:
        pid = int(raw.get("pid", 0) or 0)
    except Exception:
        pid = 0
    try:
        port = int(raw.get("port", 0) or 0)
    except Exception:
        port = 0
    return {
        "pid": pid,
        "browserUrl": str(raw.get("browserUrl", "") or "").strip(),
        "port": port,
    }


def clear_sidecar_server_process(project_dir: Path, sidecar_id: str) -> None:
    path = sidecar_server_process_path(project_dir, sidecar_id)
    try:
        path.unlink()
    except FileNotFoundError:
        return


def resolve_http_sidecar(spec: HttpSidecarSpec) -> tuple[dict[str, Any] | None, int]:
    health_payload = spec.fetch_health(spec.browser_url)
    listener_pid = find_tcp_listening_pid(spec.port)
    if health_payload is not None:
        server_pid = int((health_payload or {}).get("serverPid", 0) or 0)
        if server_pid > 0 and listener_pid == 0 and is_process_alive(server_pid):
            listener_pid = server_pid
    return health_payload, listener_pid


def record_http_sidecar(spec: HttpSidecarSpec, pid: int) -> None:
    if int(pid or 0) <= 0:
        return
    next_payload = {
        "pid": int(pid),
        "browserUrl": spec.browser_url,
        "port": int(spec.port),
    }
    current_payload = read_sidecar_server_process(spec.project_dir, spec.sidecar_id)
    if _normalized_sidecar_process_payload(current_payload) == _normalized_sidecar_process_payload(next_payload):
        return
    try:
        write_sidecar_server_process(
            spec.project_dir,
            spec.sidecar_id,
            next_payload,
        )
    except OSError:
        return


def recorded_http_sidecar_pid(spec: HttpSidecarSpec) -> int:
    payload = read_sidecar_server_process(spec.project_dir, spec.sidecar_id) or {}
    try:
        return int(payload.get("pid", 0) or 0)
    except Exception:
        return 0


def wait_for_http_sidecar_ready(
    spec: HttpSidecarSpec,
    *,
    expected_pid: int,
    timeout_seconds: float = 10.0,
    stable_seconds: float = 0.8,
) -> tuple[dict[str, Any], int] | None:
    deadline = time.time() + max(float(timeout_seconds), 0.0)
    stable_since = 0.0
    while time.time() < deadline:
        health_payload, listener_pid = resolve_http_sidecar(spec)
        health_pid = int((health_payload or {}).get("serverPid", 0) or 0)
        live_pid = listener_pid or health_pid
        if health_payload is not None and live_pid == int(expected_pid) and is_process_alive(expected_pid):
            if stable_since <= 0.0:
                stable_since = time.time()
            elif (time.time() - stable_since) >= max(float(stable_seconds), 0.0):
                return health_payload, live_pid
        else:
            stable_since = 0.0
            if expected_pid > 0 and not is_process_alive(expected_pid):
                break
        time.sleep(0.2)
    return None


def start_http_sidecar(
    spec: HttpSidecarSpec,
    *,
    child_argv: list[str],
    open_browser: bool,
    retries: int = 1,
) -> dict[str, Any]:
    health_payload, listener_pid = resolve_http_sidecar(spec)
    if health_payload is not None and listener_pid > 0 and is_process_alive(listener_pid):
        record_http_sidecar(spec, listener_pid)
        if open_browser:
            try:
                webbrowser.open(spec.browser_url)
            except Exception:
                pass
        return {
            "ok": True,
            "alreadyRunning": True,
            "pid": listener_pid,
            "browserUrl": spec.browser_url,
        }

    if health_payload is None and listener_pid <= 0:
        recorded_pid = recorded_http_sidecar_pid(spec)
        if recorded_pid > 0 and not is_process_alive(recorded_pid):
            clear_sidecar_server_process(spec.project_dir, spec.sidecar_id)

    process_pid = 0
    for attempt in range(max(int(retries), 1)):
        process_pid = spawn_background_process(
            child_argv,
            cwd=spec.project_dir,
            stdout_path=spec.stdout_log_path,
            stderr_path=spec.stderr_log_path,
            detached_from_parent_job=True,
        )
        ready = wait_for_http_sidecar_ready(spec, expected_pid=process_pid)
        if ready is not None:
            _, live_pid = ready
            record_http_sidecar(spec, live_pid)
            if open_browser:
                try:
                    webbrowser.open(spec.browser_url)
                except Exception:
                    pass
            return {
                "ok": True,
                "alreadyRunning": False,
                "pid": live_pid,
                "browserUrl": spec.browser_url,
            }
        if process_pid > 0 and is_process_alive(process_pid):
            terminate_process(process_pid)
        if attempt < max(int(retries), 1) - 1:
            time.sleep(0.8)

    return {
        "ok": False,
        "pid": process_pid,
        "browserUrl": spec.browser_url,
    }


def status_http_sidecar(spec: HttpSidecarSpec) -> dict[str, Any]:
    health_payload, listener_pid = resolve_http_sidecar(spec)
    pid = listener_pid or int((health_payload or {}).get("serverPid", 0) or 0) or recorded_http_sidecar_pid(spec)
    alive = is_process_alive(pid) if pid else False
    healthy = health_payload is not None and alive
    if healthy and pid > 0:
        record_http_sidecar(spec, pid)
    elif not alive and health_payload is None and listener_pid <= 0:
        clear_sidecar_server_process(spec.project_dir, spec.sidecar_id)
    return {
        "browserUrl": spec.browser_url,
        "healthy": healthy,
        "pid": pid or 0,
        "pidAlive": alive,
    }


def _request_http_sidecar_shutdown(browser_url: str) -> bool:
    request = Request(browser_url.rstrip("/") + "/api/shutdown", data=b"{}", method="POST")
    request.add_header("Content-Type", "application/json")
    try:
        with urlopen(request, timeout=2):
            return True
    except Exception:
        return False


def stop_http_sidecar(
    spec: HttpSidecarSpec,
    *,
    shutdown_timeout_seconds: float = 8.0,
    kill_timeout_seconds: float = 4.0,
) -> dict[str, Any]:
    health_payload, listener_pid = resolve_http_sidecar(spec)
    recorded_pid = recorded_http_sidecar_pid(spec)
    effective_pid = listener_pid or int((health_payload or {}).get("serverPid", 0) or 0) or recorded_pid

    if health_payload is None and listener_pid <= 0 and not is_process_alive(effective_pid):
        clear_sidecar_server_process(spec.project_dir, spec.sidecar_id)
        return {"ok": True, "stopped": True}

    if health_payload is not None:
        _request_http_sidecar_shutdown(spec.browser_url)
        deadline = time.time() + max(float(shutdown_timeout_seconds), 0.0)
        while time.time() < deadline:
            health_payload, listener_pid = resolve_http_sidecar(spec)
            effective_pid = listener_pid or int((health_payload or {}).get("serverPid", 0) or 0) or recorded_pid
            if health_payload is None and listener_pid <= 0 and not is_process_alive(effective_pid):
                clear_sidecar_server_process(spec.project_dir, spec.sidecar_id)
                return {"ok": True, "stopped": True}
            time.sleep(0.4)

    listener_pid = find_tcp_listening_pid(spec.port)
    effective_pid = listener_pid or recorded_pid
    if effective_pid > 0:
        terminate_process(effective_pid)
        deadline = time.time() + max(float(kill_timeout_seconds), 0.0)
        while time.time() < deadline:
            if find_tcp_listening_pid(spec.port) <= 0 and not is_process_alive(effective_pid):
                clear_sidecar_server_process(spec.project_dir, spec.sidecar_id)
                return {"ok": True, "stopped": True}
            time.sleep(0.3)

    return {"ok": False, "stopped": False}
