from __future__ import annotations

import json
import mimetypes
import os
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from .dashboard_store import (
    DEFAULT_EVENT_LIMIT,
    DEFAULT_LOG_TAIL_LINES,
    DEFAULT_QUEUE_LIMIT,
    DEFAULT_RECENT_JOB_LIMIT,
    DEFAULT_RUN_LIMIT,
    build_dashboard_run_detail_snapshot,
    build_dashboard_snapshot,
    resolve_dashboard_generated_image_artifact,
    toggle_dashboard_favorite,
)
from .dashboard_views import render_dashboard_html, render_run_detail_html


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def dashboard_browser_url(host: str, port: int) -> str:
    normalized_host = str(host or "").strip() or "127.0.0.1"
    if normalized_host in {"0.0.0.0", "::"}:
        normalized_host = "127.0.0.1"
    return f"http://{normalized_host}:{int(port)}"


def fetch_existing_dashboard_health(url: str, *, timeout_seconds: int = 2) -> dict[str, Any] | None:
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
        and str(payload.get("service", "")).strip() == "ops_dashboard"
    ):
        return None
    return payload


def probe_existing_dashboard(url: str, *, timeout_seconds: int = 2) -> bool:
    return fetch_existing_dashboard_health(url, timeout_seconds=timeout_seconds) is not None


def _make_handler(
    *,
    project_dir: Path,
    dashboard_title: str,
    refresh_seconds: int,
    queue_limit: int,
    recent_job_limit: int,
    event_limit: int,
    run_limit: int,
    log_tail_lines: int,
):
    class DashboardHandler(BaseHTTPRequestHandler):
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
            body = path.read_bytes()
            self._send_response(body=body, content_type=content_type)

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
                html = render_dashboard_html(project_name=dashboard_title, refresh_seconds=refresh_seconds)
                self._send_response(body=html.encode("utf-8"), content_type="text/html; charset=utf-8")
                return
            if parsed.path == "/runs/detail":
                query = parse_qs(parsed.query)
                run_id = str((query.get("runId") or [""])[0])
                if not run_id:
                    self._send_json({"ok": False, "error": "Missing runId"}, status=HTTPStatus.BAD_REQUEST)
                    return
                if build_dashboard_run_detail_snapshot(project_dir, run_id) is None:
                    self._send_json({"ok": False, "error": "Run not found"}, status=HTTPStatus.NOT_FOUND)
                    return
                html = render_run_detail_html(
                    project_name=dashboard_title,
                    run_id=run_id,
                    refresh_seconds=refresh_seconds,
                )
                self._send_response(body=html.encode("utf-8"), content_type="text/html; charset=utf-8")
                return
            if parsed.path == "/api/snapshot":
                snapshot = build_dashboard_snapshot(
                    project_dir,
                    queue_limit=queue_limit,
                    recent_job_limit=recent_job_limit,
                    event_limit=event_limit,
                    run_limit=run_limit,
                    log_tail_lines=log_tail_lines,
                )
                self._send_json(snapshot)
                return
            if parsed.path == "/api/run-detail":
                query = parse_qs(parsed.query)
                run_id = str((query.get("runId") or [""])[0])
                if not run_id:
                    self._send_json({"ok": False, "error": "Missing runId"}, status=HTTPStatus.BAD_REQUEST)
                    return
                snapshot = build_dashboard_run_detail_snapshot(project_dir, run_id)
                if snapshot is None:
                    self._send_json({"ok": False, "error": "Run not found"}, status=HTTPStatus.NOT_FOUND)
                    return
                self._send_json(snapshot)
                return
            if parsed.path == "/artifacts/generated-image":
                query = parse_qs(parsed.query)
                run_id = str((query.get("runId") or [""])[0])
                image_path = resolve_dashboard_generated_image_artifact(project_dir, run_id)
                if image_path is None:
                    self._send_json({"ok": False, "error": "Image not found"}, status=HTTPStatus.NOT_FOUND)
                    return
                self._send_file(image_path)
                return
            if parsed.path == "/api/healthz":
                self._send_json(
                    {
                        "ok": True,
                        "service": "ops_dashboard",
                        "projectDir": str(project_dir.resolve()),
                        "serverPid": os.getpid(),
                    }
                )
                return
            self._send_json({"ok": False, "error": "Not found"}, status=HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/api/toggle-favorite":
                try:
                    payload = self._read_json_body()
                    result = toggle_dashboard_favorite(project_dir, payload)
                except RuntimeError as exc:
                    self._send_json(
                        {"ok": False, "error": str(exc).strip() or "无法更新收藏状态。"},
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                self._send_json({"ok": True, **result})
                return
            if parsed.path == "/api/shutdown":
                self._send_json({"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            self._send_json({"ok": False, "error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    return DashboardHandler


def run_dashboard_server(
    project_dir: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    refresh_seconds: int = 5,
    queue_limit: int = DEFAULT_QUEUE_LIMIT,
    recent_job_limit: int = DEFAULT_RECENT_JOB_LIMIT,
    event_limit: int = DEFAULT_EVENT_LIMIT,
    run_limit: int = DEFAULT_RUN_LIMIT,
    log_tail_lines: int = DEFAULT_LOG_TAIL_LINES,
    open_browser: bool = False,
) -> None:
    project_dir = Path(project_dir).resolve()
    browser_url = dashboard_browser_url(host, int(port))
    snapshot = build_dashboard_snapshot(
        project_dir,
        queue_limit=queue_limit,
        recent_job_limit=recent_job_limit,
        event_limit=event_limit,
        run_limit=run_limit,
        log_tail_lines=log_tail_lines,
    )
    dashboard_title = str(snapshot.get("identity", {}).get("dashboardTitle", "")).strip() or f"{project_dir.name} 运维面板"
    try:
        server = ThreadingHTTPServer(
            (host, int(port)),
            _make_handler(
                project_dir=project_dir,
                dashboard_title=dashboard_title,
                refresh_seconds=refresh_seconds,
                queue_limit=queue_limit,
                recent_job_limit=recent_job_limit,
                event_limit=event_limit,
                run_limit=run_limit,
                log_tail_lines=log_tail_lines,
            ),
        )
    except OSError as exc:
        if probe_existing_dashboard(browser_url):
            print(f"[ops-dashboard] 检测到已有面板正在运行：{browser_url}")
            print("[ops-dashboard] 本次不会重复启动新实例，直接复用现有页面。")
            if open_browser:
                try:
                    webbrowser.open(browser_url)
                except Exception:
                    pass
            return
        raise RuntimeError(
            f"运维面板启动失败：{host}:{int(port)} 已被其他进程占用。"
        ) from exc
    server.daemon_threads = True
    print(f"[ops-dashboard] 面板地址：{browser_url}")
    print(f"[ops-dashboard] 面板标题：{dashboard_title}")
    print(f"[ops-dashboard] 项目目录：{project_dir}")
    print("[ops-dashboard] 只读观察当前 QQ 服务、队列、采样健康和最近产物。")
    if open_browser:
        try:
            webbrowser.open(browser_url)
        except Exception:
            pass
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("[ops-dashboard] 已收到退出信号，正在关闭。")
    finally:
        server.server_close()
