from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
import webbrowser
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import ProxyHandler, Request, build_opener, urlopen
from uuid import uuid4

from generation_slot import GenerationSlotBusyError, read_generation_slot
from io_utils import normalize_spaces
from process_utils import is_process_alive, spawn_background_process
from run_detail_store import build_run_detail_snapshot, resolve_generated_image_artifact
from sidecar_control import sidecar_logs_root

from test_pipeline import validate_workbench_request
from .content_workbench_store import (
    DEFAULT_HISTORY_LIMIT,
    clear_active_worker,
    build_content_workbench_snapshot,
    clear_active_request,
    clear_workbench_stop_request,
    delete_workbench_run,
    migrate_legacy_content_workbench_state,
    reconcile_workbench_runtime_state,
    read_active_worker,
    read_last_request,
    read_workbench_status,
    request_workbench_stop,
    write_active_request,
    write_active_worker,
    write_last_request,
    write_workbench_status,
)
from .content_workbench_views import render_content_workbench_html


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def content_workbench_browser_url(host: str, port: int) -> str:
    normalized_host = str(host or "").strip() or "127.0.0.1"
    if normalized_host in {"0.0.0.0", "::"}:
        normalized_host = "127.0.0.1"
    return f"http://{normalized_host}:{int(port)}"


def fetch_existing_content_workbench_health(url: str, *, timeout_seconds: int = 2) -> dict[str, Any] | None:
    health_url = url.rstrip("/") + "/api/healthz"
    request = Request(health_url, method="GET")
    try:
        host = (urlparse(request.full_url).hostname or "").strip().casefold()
        if host in {"127.0.0.1", "localhost", "::1"}:
            opener = build_opener(ProxyHandler({}))
            response = opener.open(request, timeout=timeout_seconds)
        else:
            response = urlopen(request, timeout=timeout_seconds)
        with response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, OSError, json.JSONDecodeError):
        return None
    if not (
        isinstance(payload, dict)
        and payload.get("ok") is True
        and normalize_spaces(str(payload.get("service", ""))) == "content_workbench"
    ):
        return None
    return payload


def probe_existing_content_workbench(url: str, *, timeout_seconds: int = 2) -> bool:
    return fetch_existing_content_workbench_health(url, timeout_seconds=timeout_seconds) is not None


class ContentWorkbenchManager:
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir).resolve()
        self._lock = threading.Lock()

    def _worker_log_paths(self) -> tuple[Path, Path]:
        log_dir = sidecar_logs_root(self.project_dir, "content_workbench")
        return (
            log_dir / "worker.stdout.log",
            log_dir / "worker.stderr.log",
        )

    def _active_worker_locked(self) -> dict[str, Any] | None:
        return read_active_worker(self.project_dir, cleanup_stale=True)

    def is_busy(self) -> bool:
        with self._lock:
            return self._active_worker_locked() is not None

    def _launch_worker_process(self) -> int:
        stdout_path, stderr_path = self._worker_log_paths()
        return spawn_background_process(
            [
                str(Path(sys.executable).resolve()),
                str(self.project_dir / "run_content_workbench.py"),
                "worker",
            ],
            cwd=self.project_dir,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            detached_from_parent_job=True,
        )

    def _worker_bootstrap_ready(self, *, worker_pid: int, request_id: str) -> bool:
        active_worker = read_active_worker(self.project_dir, cleanup_stale=False)
        if active_worker is not None:
            active_worker_pid = int(active_worker.get("pid", 0) or 0)
            if active_worker_pid == int(worker_pid) and is_process_alive(worker_pid):
                return True

        status_payload = read_workbench_status(self.project_dir) or {}
        status_request = status_payload.get("request", {}) if isinstance(status_payload.get("request"), dict) else {}
        if normalize_spaces(str(status_request.get("requestId", ""))) != request_id:
            return False
        try:
            status_worker_pid = int(status_payload.get("workerPid", 0) or 0)
        except (TypeError, ValueError):
            status_worker_pid = 0
        return status_worker_pid == int(worker_pid)

    def _wait_for_worker_bootstrap(self, *, worker_pid: int, request_id: str, timeout_seconds: float = 5.0) -> None:
        deadline = datetime.now().timestamp() + max(float(timeout_seconds), 0.0)
        while datetime.now().timestamp() < deadline:
            if self._worker_bootstrap_ready(worker_pid=worker_pid, request_id=request_id):
                return
            if not is_process_alive(worker_pid):
                break
            threading.Event().wait(0.1)
        if self._worker_bootstrap_ready(worker_pid=worker_pid, request_id=request_id):
            return
        raise RuntimeError("内容测试 worker 未成功启动，请查看 worker 日志。")

    def start_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized_request = {
            **validate_workbench_request(self.project_dir, payload),
            "requestId": uuid4().hex,
        }
        last_request = {key: value for key, value in normalized_request.items() if key != "requestId"}
        with self._lock:
            if self._active_worker_locked() is not None:
                raise RuntimeError("当前已有一轮内容测试正在进行，请等待完成或先停止。")
            slot_holder = read_generation_slot(self.project_dir, cleanup_stale=True)
            if slot_holder is not None:
                raise GenerationSlotBusyError(slot_holder)

            write_last_request(self.project_dir, last_request)
            write_active_request(self.project_dir, normalized_request)
            clear_workbench_stop_request(self.project_dir)
            started_at = datetime.now().isoformat(timespec="seconds")
            write_workbench_status(
                self.project_dir,
                {
                    "status": "running",
                    "stage": "准备测试输入",
                    "request": normalized_request,
                    "startedAt": started_at,
                    "runId": "",
                    "runRoot": "",
                    "error": "",
                },
            )
            try:
                worker_pid = self._launch_worker_process()
                self._wait_for_worker_bootstrap(worker_pid=worker_pid, request_id=normalized_request["requestId"])
            except Exception as exc:
                clear_active_request(self.project_dir)
                clear_active_worker(self.project_dir)
                clear_workbench_stop_request(self.project_dir)
                write_workbench_status(
                    self.project_dir,
                    {
                        "status": "failed",
                        "stage": "",
                        "request": normalized_request,
                        "startedAt": started_at,
                        "finishedAt": datetime.now().isoformat(timespec="seconds"),
                        "runId": "",
                        "runRoot": "",
                        "error": normalize_spaces(str(exc)) or "内容测试 worker 启动失败。",
                    },
                )
                raise RuntimeError(normalize_spaces(str(exc)) or "内容测试 worker 启动失败。") from exc
        return normalized_request

    def stop_task(self) -> dict[str, Any]:
        with self._lock:
            if self._active_worker_locked() is None:
                raise RuntimeError("当前没有正在运行的内容测试。")
            status_payload = read_workbench_status(self.project_dir) or {}
            if normalize_spaces(str(status_payload.get("status", ""))) == "stopping":
                return {"accepted": True, "alreadyStopping": True}
            request_workbench_stop(self.project_dir)
            write_workbench_status(
                self.project_dir,
                {
                    **status_payload,
                    "status": "stopping",
                    "stage": normalize_spaces(str(status_payload.get("stage", ""))) or "正在请求停止",
                    "error": "",
                },
            )
            return {"accepted": True, "alreadyStopping": False}

    def rerun_last(self) -> dict[str, Any]:
        payload = read_last_request(self.project_dir) or {}
        if not payload:
            raise RuntimeError("还没有可复跑的测试请求。")
        return self.start_task(payload)

    def shutdown(self, *, join_timeout: float = 2.0) -> None:
        return


def _make_handler(
    *,
    project_dir: Path,
    refresh_seconds: int,
    history_limit: int,
    manager: ContentWorkbenchManager,
):
    class ContentWorkbenchHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

        def _send_response(self, *, body: bytes, content_type: str, status: int = HTTPStatus.OK) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, payload: dict[str, Any], *, status: int = HTTPStatus.OK) -> None:
            self._send_response(
                body=_json_bytes(payload),
                content_type="application/json; charset=utf-8",
                status=status,
            )

        def _send_file(self, path: Path) -> None:
            content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            self._send_response(body=path.read_bytes(), content_type=content_type)

        def _read_json_body(self) -> dict[str, Any]:
            try:
                content_length = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError as exc:
                raise RuntimeError("请求体长度无效。") from exc
            raw = self.rfile.read(max(content_length, 0)) if content_length > 0 else b"{}"
            if not raw:
                return {}
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception as exc:
                raise RuntimeError("请求体不是合法 JSON。") from exc
            if not isinstance(payload, dict):
                raise RuntimeError("请求体顶层必须是 JSON 对象。")
            return payload

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path in ("/", "/index.html"):
                snapshot = build_content_workbench_snapshot(project_dir, history_limit=history_limit)
                title = str(snapshot.get("identity", {}).get("workbenchTitle", "")).strip() or f"{project_dir.name} 内容测试工作台"
                html = render_content_workbench_html(project_name=title, refresh_seconds=refresh_seconds)
                self._send_response(body=html.encode("utf-8"), content_type="text/html; charset=utf-8")
                return
            if parsed.path == "/api/snapshot":
                reconcile_workbench_runtime_state(project_dir)
                query = parse_qs(parsed.query)
                selected_run_id = str((query.get("selectedRunId") or [""])[0])
                snapshot = build_content_workbench_snapshot(
                    project_dir,
                    selected_run_id=selected_run_id,
                    history_limit=history_limit,
                )
                self._send_json(snapshot)
                return
            if parsed.path == "/api/run-detail":
                query = parse_qs(parsed.query)
                run_id = str((query.get("runId") or [""])[0])
                if not run_id:
                    self._send_json({"ok": False, "error": "Missing runId"}, status=HTTPStatus.BAD_REQUEST)
                    return
                snapshot = build_run_detail_snapshot(project_dir, run_id)
                if snapshot is None:
                    self._send_json({"ok": False, "error": "Run not found"}, status=HTTPStatus.NOT_FOUND)
                    return
                self._send_json(snapshot)
                return
            if parsed.path == "/artifacts/generated-image":
                query = parse_qs(parsed.query)
                run_id = str((query.get("runId") or [""])[0])
                image_path = resolve_generated_image_artifact(project_dir, run_id)
                if image_path is None:
                    self._send_json({"ok": False, "error": "Image not found"}, status=HTTPStatus.NOT_FOUND)
                    return
                self._send_file(image_path)
                return
            if parsed.path == "/api/healthz":
                reconcile_workbench_runtime_state(project_dir)
                status_payload = read_workbench_status(project_dir) or {}
                self._send_json(
                    {
                        "ok": True,
                        "service": "content_workbench",
                        "projectDir": str(project_dir),
                        "serverPid": os.getpid(),
                        "busy": manager.is_busy(),
                        "taskStatus": normalize_spaces(str(status_payload.get("status", ""))),
                        "runId": normalize_spaces(str(status_payload.get("runId", ""))),
                    }
                )
                return
            self._send_json({"ok": False, "error": "Not found"}, status=HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/api/start":
                try:
                    payload = self._read_json_body()
                    normalized_request = manager.start_task(payload)
                except RuntimeError as exc:
                    message = normalize_spaces(str(exc)) or "无法启动内容测试。"
                    status = (
                        HTTPStatus.CONFLICT
                        if ("正在进行" in message or "当前正被" in message)
                        else HTTPStatus.BAD_REQUEST
                    )
                    self._send_json({"ok": False, "error": message}, status=status)
                    return
                self._send_json({"ok": True, "request": normalized_request})
                return
            if parsed.path == "/api/stop":
                try:
                    result = manager.stop_task()
                except RuntimeError as exc:
                    self._send_json(
                        {"ok": False, "error": normalize_spaces(str(exc)) or "当前没有运行中的测试。"},
                        status=HTTPStatus.CONFLICT,
                    )
                    return
                self._send_json({"ok": True, **result})
                return
            if parsed.path == "/api/rerun-last":
                try:
                    normalized_request = manager.rerun_last()
                except RuntimeError as exc:
                    message = normalize_spaces(str(exc)) or "无法复跑上一轮测试。"
                    status = (
                        HTTPStatus.CONFLICT
                        if ("正在进行" in message or "当前正被" in message)
                        else HTTPStatus.BAD_REQUEST
                    )
                    self._send_json({"ok": False, "error": message}, status=status)
                    return
                self._send_json({"ok": True, "request": normalized_request})
                return
            if parsed.path == "/api/delete-run":
                try:
                    payload = self._read_json_body()
                    deleted = delete_workbench_run(project_dir, str(payload.get("runId", "")))
                except RuntimeError as exc:
                    message = normalize_spaces(str(exc)) or "无法删除测试目录。"
                    status = (
                        HTTPStatus.CONFLICT
                        if ("不能删除" in message or "仍在运行" in message)
                        else HTTPStatus.BAD_REQUEST
                    )
                    self._send_json({"ok": False, "error": message}, status=status)
                    return
                self._send_json({"ok": True, **deleted})
                return
            if parsed.path == "/api/shutdown":
                self._send_json({"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            self._send_json({"ok": False, "error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    return ContentWorkbenchHandler


def run_content_workbench_server(
    project_dir: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8766,
    refresh_seconds: int = 5,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
    open_browser: bool = False,
) -> None:
    project_dir = Path(project_dir).resolve()
    migrate_legacy_content_workbench_state(project_dir)
    reconcile_workbench_runtime_state(project_dir)
    browser_url = content_workbench_browser_url(host, int(port))
    manager = ContentWorkbenchManager(project_dir)
    snapshot = build_content_workbench_snapshot(project_dir, history_limit=history_limit)
    workbench_title = str(snapshot.get("identity", {}).get("workbenchTitle", "")).strip() or f"{project_dir.name} 内容测试工作台"
    try:
        server = ThreadingHTTPServer(
            (host, int(port)),
            _make_handler(
                project_dir=project_dir,
                refresh_seconds=refresh_seconds,
                history_limit=history_limit,
                manager=manager,
            ),
        )
    except OSError as exc:
        if probe_existing_content_workbench(browser_url):
            print(f"[content-workbench] 检测到已有工作台正在运行：{browser_url}")
            print("[content-workbench] 本次不会重复启动新实例，直接复用现有页面。")
            if open_browser:
                try:
                    webbrowser.open(browser_url)
                except Exception:
                    pass
            return
        raise RuntimeError(
            f"内容测试工作台启动失败：{host}:{int(port)} 已被其他进程占用。"
        ) from exc
    server.daemon_threads = True
    print(f"[content-workbench] 地址：{browser_url}")
    print(f"[content-workbench] 标题：{workbench_title}")
    print(f"[content-workbench] 项目目录：{project_dir}")
    if open_browser:
        try:
            webbrowser.open(browser_url)
        except Exception:
            pass
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("[content-workbench] 已收到退出信号，正在关闭。")
    finally:
        manager.shutdown()
        server.server_close()
