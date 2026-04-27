from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import ensure_dir, read_json, write_json
from path_policy import resolve_workspace_local_root, resolve_workspace_path


LOCAL_CONFIG_FILENAME = "targets.local.json"
EDGE_CONFIG_KEY = "edgePublish"
EDGE_MANIFEST_FILENAME = "edge_publish_manifest.json"
EDGE_STATUS_COMMAND = "python run_publish_browser_profile.py status"
EDGE_SYNC_COMMAND = "python run_publish_browser_profile.py sync-edge"
EDGE_CLEANUP_COMMAND = "python run_publish_browser_profile.py cleanup-sessions"
EDGE_SOURCE_PROFILE_DEFAULT = "Default"
EDGE_MANAGED_PROFILE_DEFAULT = "Default"
EDGE_PROFILE_FILES = (
    "Preferences",
    "Secure Preferences",
    "Login Data",
    "Login Data For Account",
    "Web Data",
)
EDGE_PROFILE_DIRS = (
    "Network",
    "Local Storage",
    "Session Storage",
)
EDGE_CRITICAL_PATHS = (
    ("Local State",),
    (EDGE_SOURCE_PROFILE_DEFAULT, "Preferences"),
    (EDGE_SOURCE_PROFILE_DEFAULT, "Network", "Cookies"),
)


@dataclass(frozen=True)
class EdgePublishProfile:
    executable_path: Path
    source_user_data_dir: Path
    source_profile_dir: str
    managed_user_data_dir: Path
    managed_profile_dir: str
    local_config_path: Path

    @property
    def source_profile_path(self) -> Path:
        return self.source_user_data_dir / self.source_profile_dir

    @property
    def managed_profile_path(self) -> Path:
        return self.managed_user_data_dir / self.managed_profile_dir

    @property
    def manifest_path(self) -> Path:
        return self.managed_user_data_dir / EDGE_MANIFEST_FILENAME


def publish_local_config_path(project_dir: Path) -> Path:
    project_root = Path(project_dir).resolve()
    return (
        resolve_workspace_local_root(project_root)
        / project_root.name
        / "publish"
        / LOCAL_CONFIG_FILENAME
    )


def load_publish_local_config(project_dir: Path) -> dict[str, Any]:
    config_path = publish_local_config_path(project_dir)
    if not config_path.exists():
        return {}
    payload = read_json(config_path)
    return payload if isinstance(payload, dict) else {}


def _resolve_edge_executable_from_path() -> Path | None:
    try:
        result = subprocess.run(
            ["where.exe", "msedge.exe"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        candidate = Path(line.strip())
        if candidate.is_file():
            return candidate.resolve()
    return None


def discover_edge_executable() -> Path | None:
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return _resolve_edge_executable_from_path()


def _default_source_user_data_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "User Data"


def _default_managed_user_data_dir(project_dir: Path) -> Path:
    project_root = Path(project_dir).resolve()
    return (
        resolve_workspace_local_root(project_root)
        / project_root.name
        / "publish"
        / "browser-auth"
        / "edge-user-data"
    )


def edge_publish_sessions_root(project_dir: Path) -> Path:
    project_root = Path(project_dir).resolve()
    return (
        resolve_workspace_local_root(project_root)
        / project_root.name
        / "publish"
        / "browser-sessions"
        / "edge"
    )


def edge_publish_target_profiles_root(project_dir: Path) -> Path:
    project_root = Path(project_dir).resolve()
    return (
        resolve_workspace_local_root(project_root)
        / project_root.name
        / "publish"
        / "browser-auth"
        / "edge-target-profiles"
    )


def _resolve_config_path_value(project_dir: Path, raw_path: str, *, fallback: Path) -> Path:
    raw_text = str(raw_path or "").strip()
    if not raw_text:
        return fallback.resolve()
    return resolve_workspace_path(project_dir, raw_text).resolve()


def load_edge_publish_profile(project_dir: Path) -> EdgePublishProfile:
    project_root = Path(project_dir).resolve()
    local_config = load_publish_local_config(project_root)
    payload = dict(local_config.get(EDGE_CONFIG_KEY, {})) if isinstance(local_config.get(EDGE_CONFIG_KEY), dict) else {}
    discovered_executable = discover_edge_executable()
    executable_path = _resolve_config_path_value(
        project_root,
        str(payload.get("executablePath", "")),
        fallback=discovered_executable or Path(""),
    )
    source_user_data_dir = _resolve_config_path_value(
        project_root,
        str(payload.get("sourceUserDataDir", "")),
        fallback=_default_source_user_data_dir(),
    )
    managed_user_data_dir = _resolve_config_path_value(
        project_root,
        str(payload.get("managedUserDataDir", "")),
        fallback=_default_managed_user_data_dir(project_root),
    )
    return EdgePublishProfile(
        executable_path=executable_path,
        source_user_data_dir=source_user_data_dir,
        source_profile_dir=str(payload.get("sourceProfileDir", EDGE_SOURCE_PROFILE_DEFAULT)).strip() or EDGE_SOURCE_PROFILE_DEFAULT,
        managed_user_data_dir=managed_user_data_dir,
        managed_profile_dir=str(payload.get("managedProfileDir", EDGE_MANAGED_PROFILE_DEFAULT)).strip() or EDGE_MANAGED_PROFILE_DEFAULT,
        local_config_path=publish_local_config_path(project_root),
    )


def persist_edge_publish_profile(project_dir: Path, profile: EdgePublishProfile) -> Path:
    config_path = profile.local_config_path
    payload = load_publish_local_config(project_dir)
    payload[EDGE_CONFIG_KEY] = {
        "executablePath": str(profile.executable_path),
        "sourceUserDataDir": str(profile.source_user_data_dir),
        "sourceProfileDir": profile.source_profile_dir,
        "managedUserDataDir": str(profile.managed_user_data_dir),
        "managedProfileDir": profile.managed_profile_dir,
    }
    write_json(config_path, payload)
    return config_path


def _manifest_matches(profile: EdgePublishProfile, payload: dict[str, Any]) -> bool:
    return (
        str(payload.get("sourceUserDataDir", "")).strip() == str(profile.source_user_data_dir)
        and str(payload.get("sourceProfileDir", "")).strip() == profile.source_profile_dir
        and str(payload.get("managedUserDataDir", "")).strip() == str(profile.managed_user_data_dir)
        and str(payload.get("managedProfileDir", "")).strip() == profile.managed_profile_dir
    )


def _try_copy_file(source: Path) -> str | None:
    if not source.exists() or not source.is_file():
        return None
    temp_dir = Path(tempfile.mkdtemp(prefix="edge-copy-check-"))
    try:
        shutil.copy2(source, temp_dir / source.name)
        return None
    except Exception as exc:
        return str(exc)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _critical_lock_errors(profile: EdgePublishProfile) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    critical_paths = [
        profile.source_user_data_dir / "Local State",
        profile.source_profile_path / "Preferences",
        profile.source_profile_path / "Network" / "Cookies",
    ]
    for source in critical_paths:
        error = _try_copy_file(source)
        if error:
            errors.append({"path": str(source), "error": error})
    return errors


def _edge_status_payload(
    *,
    profile: EdgePublishProfile,
    managed_ready: bool,
    lock_errors: list[dict[str, str]],
) -> dict[str, Any]:
    if not profile.executable_path.is_file():
        return {
            "statusCode": "missing_executable",
            "readyForPublish": False,
            "statusText": "未找到 Edge 可执行文件。",
            "guidance": f"先安装 Edge，或在 {profile.local_config_path} 写入 edgePublish.executablePath。",
            "blockingLockErrors": [],
        }
    if not profile.source_user_data_dir.exists():
        return {
            "statusCode": "missing_source_user_data",
            "readyForPublish": False,
            "statusText": "未找到 Edge 用户数据目录。",
            "guidance": f"先用 Edge 登录发布平台，再执行 {EDGE_SYNC_COMMAND}。",
            "blockingLockErrors": [],
        }
    if not profile.source_profile_path.exists():
        return {
            "statusCode": "missing_source_profile",
            "readyForPublish": False,
            "statusText": f"未找到 Edge 配置目录：{profile.source_profile_dir}",
            "guidance": f"确认 Edge 配置名后写入 {profile.local_config_path}，再执行 {EDGE_SYNC_COMMAND}。",
            "blockingLockErrors": [],
        }
    if managed_ready:
        return {
            "statusCode": "ready",
            "readyForPublish": True,
            "statusText": "Edge 发布配置已同步，可以使用浏览器草稿发布。",
            "guidance": f"登录态过期时，关闭 Edge 后重新执行 {EDGE_SYNC_COMMAND}。",
            "blockingLockErrors": [],
        }
    if lock_errors:
        first = lock_errors[0]
        return {
            "statusCode": "source_locked",
            "readyForPublish": False,
            "statusText": "Edge 登录态还没有同步，当前默认配置正被浏览器占用。",
            "guidance": f"关闭 Edge 后执行 {EDGE_SYNC_COMMAND}。锁定文件：{first['path']}",
            "blockingLockErrors": lock_errors,
        }
    return {
        "statusCode": "sync_required",
        "readyForPublish": False,
        "statusText": "Edge 登录态还没有同步到发布服务。",
        "guidance": f"执行 {EDGE_SYNC_COMMAND}，同步后回到工作台刷新发布配置。",
        "blockingLockErrors": [],
    }


def read_edge_publish_profile_status(project_dir: Path) -> dict[str, Any]:
    profile = load_edge_publish_profile(project_dir)
    manifest_payload = read_json(profile.manifest_path) if profile.manifest_path.exists() else {}
    if not isinstance(manifest_payload, dict):
        manifest_payload = {}
    lock_errors = _critical_lock_errors(profile) if profile.source_profile_path.exists() else []
    managed_ready = (
        profile.managed_user_data_dir.exists()
        and profile.managed_profile_path.exists()
        and isinstance(manifest_payload, dict)
        and bool(manifest_payload)
        and _manifest_matches(profile, manifest_payload)
    )
    status_payload = _edge_status_payload(
        profile=profile,
        managed_ready=managed_ready,
        lock_errors=lock_errors,
    )
    return {
        "browser": "edge",
        "executablePath": str(profile.executable_path),
        "executableFound": profile.executable_path.is_file(),
        "sourceUserDataDir": str(profile.source_user_data_dir),
        "sourceUserDataDirExists": profile.source_user_data_dir.exists(),
        "sourceProfileDir": profile.source_profile_dir,
        "sourceProfileExists": profile.source_profile_path.exists(),
        "managedUserDataDir": str(profile.managed_user_data_dir),
        "managedUserDataDirExists": profile.managed_user_data_dir.exists(),
        "managedProfileDir": profile.managed_profile_dir,
        "managedProfileExists": profile.managed_profile_path.exists(),
        "managedReady": managed_ready,
        "syncRequired": not managed_ready,
        "localConfigPath": str(profile.local_config_path),
        "manifestPath": str(profile.manifest_path),
        "criticalLockErrors": lock_errors,
        "statusCommand": EDGE_STATUS_COMMAND,
        "syncCommand": EDGE_SYNC_COMMAND,
        "cleanupCommand": EDGE_CLEANUP_COMMAND,
        "sessionRoot": str(edge_publish_sessions_root(project_dir)),
        **status_payload,
    }


def _copy_file(source: Path, target: Path) -> None:
    ensure_dir(target.parent)
    shutil.copy2(source, target)


def _copy_directory(source: Path, target: Path) -> None:
    if not source.exists():
        return
    ensure_dir(target.parent)
    shutil.copytree(source, target, dirs_exist_ok=True)


def _write_manifest(profile: EdgePublishProfile) -> Path:
    write_json(
        profile.manifest_path,
        {
            "browser": "edge",
            "syncedAt": datetime.now().isoformat(timespec="seconds"),
            "sourceUserDataDir": str(profile.source_user_data_dir),
            "sourceProfileDir": profile.source_profile_dir,
            "managedUserDataDir": str(profile.managed_user_data_dir),
            "managedProfileDir": profile.managed_profile_dir,
        },
    )
    return profile.manifest_path


def sync_edge_publish_profile(project_dir: Path) -> dict[str, Any]:
    profile = load_edge_publish_profile(project_dir)
    if not profile.executable_path.is_file():
        raise RuntimeError("未找到 Edge 可执行文件。")
    if not profile.source_user_data_dir.exists():
        raise RuntimeError("未找到 Edge 用户数据目录。")
    if not profile.source_profile_path.exists():
        raise RuntimeError(f"未找到 Edge 配置目录：{profile.source_profile_dir}")
    lock_errors = _critical_lock_errors(profile)
    if lock_errors:
        first = lock_errors[0]
        raise RuntimeError(
            "当前 Edge 默认配置仍被浏览器占用。请先关闭 Edge，再执行一次同步。"
            f" 锁定文件：{first['path']}"
        )

    persist_edge_publish_profile(project_dir, profile)
    if profile.managed_user_data_dir.exists():
        shutil.rmtree(profile.managed_user_data_dir, ignore_errors=True)
    ensure_dir(profile.managed_profile_path)
    _copy_file(profile.source_user_data_dir / "Local State", profile.managed_user_data_dir / "Local State")
    for name in EDGE_PROFILE_FILES:
        source = profile.source_profile_path / name
        if source.exists():
            _copy_file(source, profile.managed_profile_path / name)
    for name in EDGE_PROFILE_DIRS:
        source = profile.source_profile_path / name
        if source.exists():
            _copy_directory(source, profile.managed_profile_path / name)
    manifest_path = _write_manifest(profile)
    return {
        "browser": "edge",
        "managedUserDataDir": str(profile.managed_user_data_dir),
        "managedProfileDir": profile.managed_profile_dir,
        "manifestPath": str(manifest_path),
        "localConfigPath": str(profile.local_config_path),
    }


def _terminate_edge_processes_for_path(path: Path) -> None:
    if os.name != "nt":
        return
    escaped_path = str(path).replace("'", "''")
    script = (
        f"$target = '{escaped_path}'; "
        "Get-CimInstance Win32_Process -Filter \"name='msedge.exe'\" | "
        "Where-Object { $_.CommandLine -like \"*$target*\" } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


def _windows_extended_path(path: Path) -> str:
    resolved = str(Path(path).resolve())
    if os.name != "nt" or resolved.startswith("\\\\?\\"):
        return resolved
    return "\\\\?\\" + resolved


def _rmtree_best_effort(path: Path) -> None:
    def handle_remove_error(function, failed_path, exc_info) -> None:
        error = exc_info[1]
        if isinstance(error, FileNotFoundError):
            return
        try:
            os.chmod(failed_path, 0o700)
            function(failed_path)
        except FileNotFoundError:
            return

    for attempt in range(3):
        try:
            if sys.version_info >= (3, 12):
                shutil.rmtree(
                    path,
                    onexc=lambda function, failed_path, exc: None
                    if isinstance(exc, FileNotFoundError)
                    else handle_remove_error(function, failed_path, (type(exc), exc, exc.__traceback__)),
                )
            else:
                shutil.rmtree(path, onerror=handle_remove_error)
            if not path.exists():
                return
        except FileNotFoundError:
            return
        except OSError:
            if attempt == 2:
                break
        time.sleep(0.5)

    if path.exists():
        walk_root = _windows_extended_path(path)
        for root, dirs, files in os.walk(walk_root, topdown=False):
            root_path = Path(root)
            for file_name in files:
                try:
                    file_path = root_path / file_name
                    os.chmod(file_path, 0o700)
                    file_path.unlink()
                except FileNotFoundError:
                    pass
            for dir_name in dirs:
                try:
                    (root_path / dir_name).rmdir()
                except FileNotFoundError:
                    pass
                except OSError:
                    pass
        try:
            path.rmdir()
        except FileNotFoundError:
            return


def cleanup_edge_publish_sessions(project_dir: Path) -> dict[str, Any]:
    sessions_root = edge_publish_sessions_root(project_dir)
    removed: list[str] = []
    skipped: list[dict[str, str]] = []
    _terminate_edge_processes_for_path(sessions_root)
    if sessions_root.exists():
        for session_dir in sessions_root.iterdir():
            if not session_dir.is_dir():
                continue
            try:
                _rmtree_best_effort(session_dir)
                removed.append(str(session_dir))
            except Exception as exc:
                skipped.append({"path": str(session_dir), "error": str(exc)})
    return {
        "browser": "edge",
        "sessionRoot": str(sessions_root),
        "removedCount": len(removed),
        "skippedCount": len(skipped),
        "removed": removed,
        "skipped": skipped,
    }


def cleanup_stale_edge_publish_sessions(project_dir: Path, *, max_age_seconds: int) -> dict[str, Any]:
    sessions_root = edge_publish_sessions_root(project_dir)
    removed: list[str] = []
    skipped: list[dict[str, str]] = []
    if not sessions_root.exists():
        return {
            "browser": "edge",
            "sessionRoot": str(sessions_root),
            "removedCount": 0,
            "skippedCount": 0,
            "removed": removed,
            "skipped": skipped,
        }

    cutoff = time.time() - max(int(max_age_seconds), 60)
    for session_dir in sessions_root.iterdir():
        if not session_dir.is_dir():
            continue
        try:
            if session_dir.stat().st_mtime > cutoff:
                continue
            _terminate_edge_processes_for_path(session_dir)
            _rmtree_best_effort(session_dir)
            removed.append(str(session_dir))
        except Exception as exc:
            skipped.append({"path": str(session_dir), "error": str(exc)})
    return {
        "browser": "edge",
        "sessionRoot": str(sessions_root),
        "removedCount": len(removed),
        "skippedCount": len(skipped),
        "removed": removed,
        "skipped": skipped,
    }
