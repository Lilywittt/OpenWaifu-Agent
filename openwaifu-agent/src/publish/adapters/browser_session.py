from __future__ import annotations

import os
import socket
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from io_utils import ensure_dir
from process_utils import is_process_alive, terminate_process_tree
from publish.browser_profiles import (
    EDGE_PROFILE_DIRS,
    EDGE_PROFILE_FILES,
    edge_publish_sessions_root,
    load_edge_publish_profile,
    read_edge_publish_profile_status,
)
from runtime_layout import sanitize_segment


DEFAULT_BROWSER_TIMEOUT_MS = 45000
SHORT_ACTION_TIMEOUT_MS = 5000


def should_keep_browser_open(target_config: dict[str, Any]) -> bool:
    if "keepBrowserOpen" in target_config:
        return bool(target_config.get("keepBrowserOpen"))
    return not bool(target_config.get("autoSubmit", False))


@dataclass
class BrowserAutomationSession:
    playwright: Any
    browser: Any
    context: Any
    page: Any
    process: subprocess.Popen | None
    remote_debugging_port: int
    user_data_dir: Path

    def disconnect(self, *, close_browser: bool = False) -> None:
        if close_browser:
            try:
                self.browser.close()
            except Exception:
                pass
            if self.process is not None:
                try:
                    if self.process.poll() is None:
                        self.process.terminate()
                except Exception:
                    pass
                try:
                    self.process.wait(timeout=3)
                except Exception:
                    try:
                        terminate_process_tree(int(self.process.pid))
                    except Exception:
                        pass
            else:
                _terminate_edge_processes_for_user_data_dir(self.user_data_dir)
        try:
            self.playwright.stop()
        except Exception:
            pass
        if close_browser and self.process is not None:
            try:
                if is_process_alive(int(self.process.pid)):
                    terminate_process_tree(int(self.process.pid))
            except Exception:
                pass


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_cdp(port: int, timeout_seconds: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    version_url = f"http://127.0.0.1:{port}/json/version"
    while time.monotonic() < deadline:
        try:
            with urlopen(version_url, timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, URLError):
            time.sleep(0.2)
    raise RuntimeError("Edge 调试端口未按时就绪。")


def _edge_debugging_port_for_user_data_dir(user_data_dir: Path) -> int | None:
    if os.name != "nt":
        return None
    target = str(Path(user_data_dir).resolve())
    escaped_target = target.replace("'", "''")
    script = (
        f"$target = '{escaped_target}'; "
        "Get-CimInstance Win32_Process -Filter \"name='msedge.exe'\" | "
        "Where-Object { $_.CommandLine -and $_.CommandLine.Contains($target) -and $_.CommandLine.Contains('--remote-debugging-port=') } | "
        "Select-Object -First 1 -ExpandProperty CommandLine"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    command_line = result.stdout.strip()
    marker = "--remote-debugging-port="
    if result.returncode != 0 or marker not in command_line:
        return None
    raw_port = command_line.split(marker, 1)[1].split()[0].strip().strip('"')
    try:
        return int(raw_port)
    except ValueError:
        return None


def _terminate_edge_processes_for_user_data_dir(user_data_dir: Path) -> None:
    if os.name != "nt":
        return
    target = str(Path(user_data_dir).resolve())
    escaped_target = target.replace("'", "''")
    script = (
        f"$target = '{escaped_target}'; "
        "Get-CimInstance Win32_Process -Filter \"name='msedge.exe'\" | "
        "Where-Object { $_.CommandLine -and $_.CommandLine.Contains($target) } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        pass


def _create_edge_session_dir(
    project_dir: Path,
    profile,
    session_name: str = "",
    session_user_data_dir: Path | None = None,
    persistent_user_data_dir: bool = False,
) -> Path:
    timestamp = time.strftime("%Y%m%dT%H%M%S")
    suffix = sanitize_segment(session_name) if session_name else uuid.uuid4().hex[:8]
    if session_user_data_dir is None:
        session_user_data_dir = edge_publish_sessions_root(project_dir) / f"{timestamp}_{suffix}_{uuid.uuid4().hex[:8]}"
    else:
        session_user_data_dir = Path(session_user_data_dir).resolve()
    ensure_dir(session_user_data_dir)
    if persistent_user_data_dir and (session_user_data_dir / "Local State").exists() and (
        session_user_data_dir / profile.managed_profile_dir
    ).exists():
        return session_user_data_dir
    session_profile_dir = session_user_data_dir / profile.managed_profile_dir
    ensure_dir(session_profile_dir)
    shutil.copy2(profile.managed_user_data_dir / "Local State", session_user_data_dir / "Local State")
    for name in EDGE_PROFILE_FILES:
        source = profile.managed_profile_path / name
        if source.exists():
            shutil.copy2(source, session_profile_dir / name)
    for name in EDGE_PROFILE_DIRS:
        source = profile.managed_profile_path / name
        if source.exists():
            shutil.copytree(source, session_profile_dir / name, dirs_exist_ok=True)
    return session_user_data_dir


def _connect_edge_session(
    profile,
    *,
    port: int,
    url: str,
    process: subprocess.Popen | None,
    user_data_dir: Path,
) -> BrowserAutomationSession:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise RuntimeError("Playwright 未安装，无法执行浏览器发布。") from exc
    playwright = sync_playwright().start()
    browser = playwright.chromium.connect_over_cdp(
        f"http://127.0.0.1:{port}",
        timeout=DEFAULT_BROWSER_TIMEOUT_MS,
    )
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.pages[0] if context.pages else context.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=DEFAULT_BROWSER_TIMEOUT_MS)
    except Exception:
        pass
    return BrowserAutomationSession(
        playwright=playwright,
        browser=browser,
        context=context,
        page=page,
        process=process,
        remote_debugging_port=port,
        user_data_dir=user_data_dir,
    )


def open_edge_page(
    project_dir: Path,
    url: str,
    *,
    session_name: str = "",
    session_user_data_dir: Path | None = None,
    persistent_user_data_dir: bool = False,
) -> BrowserAutomationSession:
    status = read_edge_publish_profile_status(project_dir)
    if not status.get("readyForPublish"):
        guidance = str(status.get("guidance", "")).strip()
        raise RuntimeError(guidance or "Edge 发布配置未同步，请先执行 run_publish_browser_profile.py sync-edge。")
    profile = load_edge_publish_profile(project_dir)
    session_user_data_dir = _create_edge_session_dir(
        project_dir,
        profile,
        session_name=session_name,
        session_user_data_dir=session_user_data_dir,
        persistent_user_data_dir=persistent_user_data_dir,
    )
    if persistent_user_data_dir:
        existing_port = _edge_debugging_port_for_user_data_dir(session_user_data_dir)
        if existing_port is not None:
            try:
                _wait_for_cdp(existing_port, timeout_seconds=3)
                return _connect_edge_session(
                    profile,
                    port=existing_port,
                    url=url,
                    process=None,
                    user_data_dir=session_user_data_dir,
                )
            except Exception:
                pass
    port = _free_port()
    argv = [
        str(profile.executable_path),
        f"--user-data-dir={session_user_data_dir}",
        f"--profile-directory={profile.managed_profile_dir}",
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--disable-first-run-ui",
    ]
    process = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _wait_for_cdp(port)
        return _connect_edge_session(
            profile,
            port=port,
            url=url,
            process=process,
            user_data_dir=session_user_data_dir,
        )
    except Exception:
        try:
            process.terminate()
        except Exception:
            pass
        raise
