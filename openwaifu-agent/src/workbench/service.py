from __future__ import annotations

import json
import mimetypes
import os
import threading
import time
import webbrowser
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import ProxyHandler, Request, build_opener, urlopen
from uuid import uuid4

from generation_slot import GenerationSlotBusyError, read_generation_slot
from io_utils import normalize_spaces
from process_utils import is_process_alive, spawn_background_process, terminate_process_tree
from review_favorites import FAVORITE_KIND_PATH, favorite_selection_key, find_review_favorite
from run_detail_store import (
    build_run_detail_snapshot,
    build_run_detail_snapshot_from_path,
    resolve_generated_image_artifact,
)
from sidecar_control import sidecar_logs_root
from test_pipeline import validate_workbench_request
from workbench.identity import WorkbenchViewer, resolve_workbench_viewer
from workbench.profile import PRIVATE_PROFILE, WorkbenchProfile
from .store import (
    DEFAULT_HISTORY_LIMIT,
    record_terminal_workbench_payload,
    build_content_workbench_snapshot,
    can_access_workbench_run,
    clear_active_request,
    clear_active_worker,
    clear_workbench_stop_request,
    delete_workbench_run,
    finalize_workbench_runtime,
    migrate_legacy_content_workbench_state,
    read_active_request,
    read_active_worker,
    read_last_request,
    read_workbench_status,
    reconcile_workbench_runtime_state,
    request_workbench_stop,
    toggle_workbench_favorite,
    write_active_request,
    write_active_worker,
    write_last_request,
    write_workbench_status,
)
from .views import render_content_workbench_html


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def workbench_browser_url(host: str, port: int) -> str:
    normalized_host = str(host or "").strip() or "127.0.0.1"
    if normalized_host in {"0.0.0.0", "::"}:
        normalized_host = "127.0.0.1"
    return f"http://{normalized_host}:{int(port)}"


def fetch_existing_workbench_health(
    url: str,
    *,
    expected_service: str,
    timeout_seconds: int = 2,
) -> dict[str, Any] | None:
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
        and normalize_spaces(str(payload.get("service", ""))) == expected_service
    ):
        return None
    return payload


def probe_existing_workbench(url: str, *, expected_service: str, timeout_seconds: int = 2) -> bool:
    return fetch_existing_workbench_health(url, expected_service=expected_service, timeout_seconds=timeout_seconds) is not None


class WorkbenchManager:
    def __init__(
        self,
        project_dir: Path,
        *,
        profile: WorkbenchProfile,
        worker_command_builder: Callable[[str], Sequence[str]],
    ):
        self.project_dir = Path(project_dir).resolve()
        self.profile = profile
        self.worker_command_builder = worker_command_builder
        self._lock = threading.Lock()

    def _worker_log_paths(self) -> tuple[Path, Path]:
        log_dir = sidecar_logs_root(self.project_dir, self.profile.sidecar_id)
        return (log_dir / "worker.stdout.log", log_dir / "worker.stderr.log")

    def _active_worker_locked(self) -> dict[str, Any] | None:
        return read_active_worker(self.project_dir, cleanup_stale=True)

    def is_busy(self) -> bool:
        with self._lock:
            return self._active_worker_locked() is not None

    def _launch_worker_process(self, *, request_id: str) -> int:
        stdout_path, stderr_path = self._worker_log_paths()
        return spawn_background_process(
            list(self.worker_command_builder(request_id)),
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
        raise RuntimeError("内容工作台 worker 未成功启动，请查看 worker 日志。")

    def _assert_public_source_allowed(self, request: dict[str, Any]) -> None:
        if self.profile.allows_all_source_kinds:
            return
        source_kind = normalize_spaces(str(request.get("sourceKind", "")))
        if source_kind not in self.profile.allowed_source_kinds:
            raise RuntimeError("当前公共体验模式不支持这种输入方式。")

    def _can_control_current_task(self, viewer: WorkbenchViewer) -> bool:
        return not self.profile.public

    def _force_stop_active_worker(self, *, status_payload: dict[str, Any], active_worker: dict[str, Any]) -> None:
        worker_pid = int(active_worker.get("pid", 0) or 0)
        if worker_pid > 0:
            terminate_process_tree(worker_pid)
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                if not is_process_alive(worker_pid):
                    break
                time.sleep(0.1)
            if is_process_alive(worker_pid):
                raise RuntimeError("当前任务仍未退出，请稍后再试。")
        request = status_payload.get("request", {}) if isinstance(status_payload.get("request"), dict) else {}
        record_terminal_workbench_payload(
            self.project_dir,
            {
                **status_payload,
                "status": "interrupted",
                "stage": "",
                "request": request,
                "finishedAt": datetime.now().isoformat(timespec="seconds"),
                "error": "当前内容生成已被强制停止。",
            },
        )
        finalize_workbench_runtime(self.project_dir)
        read_generation_slot(self.project_dir, cleanup_stale=True)

    def start_task(self, payload: dict[str, Any], *, viewer: WorkbenchViewer) -> dict[str, Any]:
        normalized_request = {
            **validate_workbench_request(self.project_dir, payload),
            "requestId": uuid4().hex,
            "ownerId": viewer.owner_id,
            "ownerDisplay": viewer.display_name,
        }
        self._assert_public_source_allowed(normalized_request)
        last_request = {key: value for key, value in normalized_request.items() if key != "requestId"}
        with self._lock:
            if self._active_worker_locked() is not None:
                raise RuntimeError("当前已有一轮内容生成正在进行，请等待完成后再试。")
            slot_holder = read_generation_slot(self.project_dir, cleanup_stale=True)
            if slot_holder is not None:
                raise GenerationSlotBusyError(slot_holder)
            write_last_request(self.project_dir, last_request, owner_id=viewer.owner_id)
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
                worker_pid = self._launch_worker_process(request_id=normalized_request["requestId"])
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
                        "error": normalize_spaces(str(exc)) or "内容工作台 worker 启动失败。",
                    },
                )
                raise RuntimeError(normalize_spaces(str(exc)) or "内容工作台 worker 启动失败。") from exc
        return normalized_request

    def stop_task(self, *, viewer: WorkbenchViewer) -> dict[str, Any]:
        with self._lock:
            if self.profile.public:
                raise RuntimeError("内容体验工作台不提供停止任务。")
            active_worker = self._active_worker_locked()
            if active_worker is None:
                raise RuntimeError("当前没有正在运行的内容生成任务。")
            if not self._can_control_current_task(viewer):
                raise RuntimeError("当前运行中的任务不属于你，不能停止。")
            status_payload = read_workbench_status(self.project_dir) or {}
            if normalize_spaces(str(status_payload.get("status", ""))) == "stopping":
                self._force_stop_active_worker(status_payload=status_payload, active_worker=active_worker)
                return {"accepted": True, "alreadyStopping": True, "forced": True}
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
            return {"accepted": True, "alreadyStopping": False, "forced": False}

    def rerun_last(self, *, viewer: WorkbenchViewer) -> dict[str, Any]:
        payload = read_last_request(self.project_dir, owner_id=viewer.owner_id) or {}
        if not payload:
            raise RuntimeError("还没有可复跑的上一轮请求。")
        return self.start_task(payload, viewer=viewer)

    def shutdown(self) -> None:
        return


def _send_permission_error(handler: BaseHTTPRequestHandler, message: str) -> None:
    body = _json_bytes({"ok": False, "error": message})
    handler.send_response(HTTPStatus.FORBIDDEN)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Connection", "close")
    handler.close_connection = True
    handler.end_headers()
    handler.wfile.write(body)


def _make_handler(
    *,
    project_dir: Path,
    refresh_seconds: int,
    history_limit: int,
    manager: WorkbenchManager,
    profile: WorkbenchProfile,
):
    class WorkbenchHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

        def _viewer(self) -> WorkbenchViewer:
            return resolve_workbench_viewer(
                profile,
                headers=self.headers,
                client_address=self.client_address[0] if self.client_address else "",
            )

        def _send_response(self, *, body: bytes, content_type: str, status: int = HTTPStatus.OK) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()

        def _send_json(self, payload: dict[str, Any], *, status: int = HTTPStatus.OK) -> None:
            self._send_response(
                body=_json_bytes(payload),
                content_type="application/json; charset=utf-8",
                status=status,
            )

        def _send_file(self, path: Path) -> None:
            content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            file_size = path.stat().st_size
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.close_connection = True
            self.end_headers()
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            self.wfile.flush()

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

        def _discard_request_body(self) -> None:
            try:
                content_length = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError:
                content_length = 0
            if content_length > 0:
                self.rfile.read(content_length)

        def do_GET(self) -> None:  # noqa: N802
            viewer = self._viewer()
            parsed = urlparse(self.path)
            if parsed.path in ("/", "/index.html"):
                snapshot = build_content_workbench_snapshot(
                    project_dir,
                    history_limit=history_limit,
                    viewer=viewer,
                    profile=profile,
                )
                title = str(snapshot.get("identity", {}).get("workbenchTitle", "")).strip() or f"{project_dir.name} {profile.title}"
                html = render_content_workbench_html(project_name=title, refresh_seconds=refresh_seconds)
                self._send_response(body=html.encode("utf-8"), content_type="text/html; charset=utf-8")
                return
            if parsed.path == "/api/snapshot":
                reconcile_workbench_runtime_state(project_dir)
                query = parse_qs(parsed.query)
                selected_run_id = str((query.get("selectedRunId") or [""])[0])
                history_filter = str((query.get("historyFilter") or ["active"])[0])
                history_limit_raw = str((query.get("historyLimit") or [str(history_limit)])[0])
                try:
                    history_limit_value = int(history_limit_raw)
                except (TypeError, ValueError):
                    history_limit_value = history_limit
                snapshot = build_content_workbench_snapshot(
                    project_dir,
                    selected_run_id=selected_run_id,
                    history_filter=history_filter,
                    history_limit=history_limit_value,
                    viewer=viewer,
                    profile=profile,
                )
                self._send_json(snapshot)
                return
            if parsed.path == "/api/run-detail":
                query = parse_qs(parsed.query)
                run_id = str((query.get("runId") or [""])[0])
                if not run_id:
                    self._send_json({"ok": False, "error": "Missing runId"}, status=HTTPStatus.BAD_REQUEST)
                    return
                if not can_access_workbench_run(project_dir, run_id, viewer=viewer, profile=profile):
                    self._send_json({"ok": False, "error": "Run not found"}, status=HTTPStatus.NOT_FOUND)
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
                if not can_access_workbench_run(project_dir, run_id, viewer=viewer, profile=profile):
                    self._send_json({"ok": False, "error": "Image not found"}, status=HTTPStatus.NOT_FOUND)
                    return
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
                        "service": profile.sidecar_id,
                        "projectDir": str(project_dir),
                        "serverPid": os.getpid(),
                        "busy": manager.is_busy(),
                        "taskStatus": normalize_spaces(str(status_payload.get("status", ""))),
                        "runId": normalize_spaces(str(status_payload.get("runId", ""))),
                        "profile": profile.profile_id,
                    }
                )
                return
            self._send_json({"ok": False, "error": "Not found"}, status=HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            viewer = self._viewer()
            parsed = urlparse(self.path)
            if parsed.path == "/api/start":
                try:
                    payload = self._read_json_body()
                    normalized_request = manager.start_task(payload, viewer=viewer)
                except RuntimeError as exc:
                    message = normalize_spaces(str(exc)) or "无法启动内容生成任务。"
                    status = HTTPStatus.CONFLICT if "正在进行" in message or "执行位" in message else HTTPStatus.BAD_REQUEST
                    self._send_json({"ok": False, "error": message}, status=status)
                    return
                self._send_json({"ok": True, "request": normalized_request})
                return
            if parsed.path == "/api/stop":
                try:
                    result = manager.stop_task(viewer=viewer)
                except RuntimeError as exc:
                    self._send_json(
                        {"ok": False, "error": normalize_spaces(str(exc)) or "当前没有运行中的任务。"},
                        status=HTTPStatus.CONFLICT,
                    )
                    return
                self._send_json({"ok": True, **result})
                return
            if parsed.path == "/api/rerun-last":
                try:
                    normalized_request = manager.rerun_last(viewer=viewer)
                except RuntimeError as exc:
                    message = normalize_spaces(str(exc)) or "无法复跑上一轮请求。"
                    status = HTTPStatus.CONFLICT if "正在进行" in message or "执行位" in message else HTTPStatus.BAD_REQUEST
                    self._send_json({"ok": False, "error": message}, status=status)
                    return
                self._send_json({"ok": True, "request": normalized_request})
                return
            if parsed.path == "/api/delete-run":
                if not profile.allow_delete_run:
                    self._discard_request_body()
                    _send_permission_error(self, "当前模式不允许删除运行目录。")
                    return
                try:
                    payload = self._read_json_body()
                    deleted = delete_workbench_run(project_dir, str(payload.get("runId", "")))
                except RuntimeError as exc:
                    message = normalize_spaces(str(exc)) or "无法删除测试目录。"
                    status = HTTPStatus.CONFLICT if "不能删除" in message or "仍在运行" in message else HTTPStatus.BAD_REQUEST
                    self._send_json({"ok": False, "error": message}, status=status)
                    return
                self._send_json({"ok": True, **deleted})
                return
            if parsed.path == "/api/review-path":
                if not profile.allow_review_path:
                    self._discard_request_body()
                    _send_permission_error(self, "当前模式不允许审阅本地路径。")
                    return
                try:
                    payload = self._read_json_body()
                except RuntimeError as exc:
                    self._send_json(
                        {"ok": False, "error": normalize_spaces(str(exc)) or "请求体无效。"},
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                review_path = normalize_spaces(str(payload.get("path", "")))
                if not review_path:
                    self._send_json({"ok": False, "error": "路径不能为空。"}, status=HTTPStatus.BAD_REQUEST)
                    return
                detail = build_run_detail_snapshot_from_path(project_dir, review_path)
                if detail is None:
                    self._send_json({"ok": False, "error": "未找到可审阅的目录或 run。"}, status=HTTPStatus.NOT_FOUND)
                    return
                selection_key = favorite_selection_key(FAVORITE_KIND_PATH, review_path)
                favorite_entry = find_review_favorite(project_dir, selection_key=selection_key)
                self._send_json(
                    {
                        "ok": True,
                        "detail": {
                            **detail,
                            "favorite": favorite_entry is not None,
                            "favoriteKind": FAVORITE_KIND_PATH,
                            "favoriteSelectionKey": selection_key,
                            "reviewPath": review_path,
                        },
                        "favorite": favorite_entry is not None,
                        "selectionKey": selection_key,
                        "path": review_path,
                    }
                )
                return
            if parsed.path == "/api/toggle-favorite":
                if not profile.allow_favorites:
                    self._discard_request_body()
                    _send_permission_error(self, "当前模式不允许修改收藏。")
                    return
                try:
                    payload = self._read_json_body()
                    result = toggle_workbench_favorite(project_dir, payload)
                except RuntimeError as exc:
                    self._send_json(
                        {"ok": False, "error": normalize_spaces(str(exc)) or "无法更新收藏状态。"},
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                self._send_json({"ok": True, **result})
                return
            if parsed.path == "/api/shutdown":
                if profile.public:
                    self._discard_request_body()
                    _send_permission_error(self, "当前模式不允许关闭服务。")
                    return
                self._send_json({"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            self._send_json({"ok": False, "error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    return WorkbenchHandler


def run_workbench_server(
    project_dir: Path,
    *,
    profile: WorkbenchProfile,
    worker_command_builder: Callable[[str], Sequence[str]],
    host: str,
    port: int,
    refresh_seconds: int = 5,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
    open_browser: bool = False,
) -> None:
    project_dir = Path(project_dir).resolve()
    migrate_legacy_content_workbench_state(project_dir)
    reconcile_workbench_runtime_state(project_dir)
    browser_url = workbench_browser_url(host, int(port))
    manager = WorkbenchManager(
        project_dir,
        profile=profile,
        worker_command_builder=worker_command_builder,
    )
    snapshot = build_content_workbench_snapshot(
        project_dir,
        history_limit=history_limit,
        profile=profile,
    )
    workbench_title = str(snapshot.get("identity", {}).get("workbenchTitle", "")).strip() or f"{project_dir.name} {profile.title}"
    try:
        server = ThreadingHTTPServer(
            (host, int(port)),
            _make_handler(
                project_dir=project_dir,
                refresh_seconds=refresh_seconds,
                history_limit=history_limit,
                manager=manager,
                profile=profile,
            ),
        )
    except OSError as exc:
        if probe_existing_workbench(browser_url, expected_service=profile.sidecar_id):
            print(f"[{profile.sidecar_id}] 复用已启动实例：{browser_url}")
            if open_browser:
                try:
                    webbrowser.open(browser_url)
                except Exception:
                    pass
            return
        raise RuntimeError(f"{profile.title} 启动失败：{host}:{int(port)} 已被其他进程占用。") from exc
    server.daemon_threads = True
    print(f"[{profile.sidecar_id}] 地址：{browser_url}")
    print(f"[{profile.sidecar_id}] 标题：{workbench_title}")
    print(f"[{profile.sidecar_id}] 项目目录：{project_dir}")
    if open_browser:
        try:
            webbrowser.open(browser_url)
        except Exception:
            pass
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print(f"[{profile.sidecar_id}] 正在关闭。")
    finally:
        manager.shutdown()
        server.server_close()
