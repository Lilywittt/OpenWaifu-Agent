from __future__ import annotations

import socket
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from io_utils import ensure_dir
from publish.browser_profiles import (
    EDGE_PROFILE_DIRS,
    EDGE_PROFILE_FILES,
    edge_publish_sessions_root,
    load_edge_publish_profile,
    read_edge_publish_profile_status,
)
from runtime_layout import sanitize_segment


DEFAULT_BROWSER_TIMEOUT_MS = 45000


@dataclass
class BrowserAutomationSession:
    playwright: Any
    browser: Any
    context: Any
    page: Any
    process: subprocess.Popen | None
    remote_debugging_port: int
    user_data_dir: Path

    def disconnect(self) -> None:
        try:
            self.playwright.stop()
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


def _create_edge_session_dir(
    project_dir: Path,
    profile,
    session_name: str = "",
    session_user_data_dir: Path | None = None,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    suffix = sanitize_segment(session_name) if session_name else uuid.uuid4().hex[:8]
    if session_user_data_dir is None:
        session_user_data_dir = edge_publish_sessions_root(project_dir) / f"{timestamp}_{suffix}_{uuid.uuid4().hex[:8]}"
    else:
        session_user_data_dir = Path(session_user_data_dir).resolve()
    ensure_dir(session_user_data_dir)
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
    )
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


def publish_title(publish_input: dict[str, Any], target_config: dict[str, Any]) -> str:
    configured = str(target_config.get("title", "")).strip()
    if configured:
        return configured
    return (
        str(publish_input.get("scenePremiseZh", "")).strip()
        or str(publish_input.get("subjectDisplayNameZh", "")).strip()
        or str(publish_input.get("runId", "")).strip()
    )


def publish_caption(publish_input: dict[str, Any], target_config: dict[str, Any]) -> str:
    caption_prefix = str(target_config.get("captionPrefix", "")).strip()
    caption_suffix = str(target_config.get("captionSuffix", "")).strip()
    text = str(publish_input.get("socialPostText", "")).strip()
    parts = [part for part in (caption_prefix, text, caption_suffix) if part]
    return "\n\n".join(parts)


def publish_tags(publish_input: dict[str, Any], target_config: dict[str, Any]) -> list[str]:
    raw_tags = target_config.get("tags", [])
    if not isinstance(raw_tags, list):
        return []
    tags: list[str] = []
    seen: set[str] = set()
    for item in raw_tags:
        tag = str(item).strip().lstrip("#")
        key = tag.casefold()
        if not tag or key in seen:
            continue
        tags.append(tag)
        seen.add(key)
    return tags


def receipt_base(
    *,
    target_id: str,
    adapter: str,
    status: str,
    page_url: str,
    port: int,
    user_data_dir: Path | str = "",
) -> dict[str, Any]:
    payload = {
        "targetId": target_id,
        "adapter": adapter,
        "status": status,
        "publishedAt": datetime.now().isoformat(timespec="seconds"),
        "postUrl": page_url,
        "browser": "edge",
        "remoteDebuggingPort": port,
    }
    if user_data_dir:
        payload["browserUserDataDir"] = str(user_data_dir)
    return payload


def set_file_input(page: Any, image_path: Path) -> bool:
    try:
        input_locator = page.locator("input[type='file']").first
        input_locator.set_input_files(str(image_path), timeout=DEFAULT_BROWSER_TIMEOUT_MS)
        return True
    except Exception:
        return False


def fill_first_locator(page: Any, selectors: list[str], value: str) -> bool:
    if not value:
        return False
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() <= 0:
                continue
            locator.fill(value, timeout=5000)
            return True
        except Exception:
            continue
    return False


def click_text_candidates(page: Any, labels: list[str], timeout_ms: int = 5000) -> bool:
    for label in labels:
        try:
            page.get_by_text(label, exact=False).first.click(timeout=timeout_ms)
            return True
        except Exception:
            continue
    return False
