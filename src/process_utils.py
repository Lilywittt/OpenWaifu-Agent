from __future__ import annotations

import os
import subprocess
import time
import ctypes
from pathlib import Path
from typing import Any


def build_windows_background_popen_kwargs() -> dict[str, Any]:
    if os.name != "nt":
        return {}

    creationflags = 0
    for flag_name in ("CREATE_NO_WINDOW",):
        creationflags |= int(getattr(subprocess, flag_name, 0) or 0)

    kwargs: dict[str, Any] = {}
    if creationflags:
        kwargs["creationflags"] = creationflags

    startupinfo_factory = getattr(subprocess, "STARTUPINFO", None)
    if startupinfo_factory is not None:
        startupinfo = startupinfo_factory()
        startupinfo.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 0) or 0)
        startupinfo.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0) or 0)
        kwargs["startupinfo"] = startupinfo

    return kwargs


def build_windows_detached_popen_kwargs() -> dict[str, Any]:
    if os.name != "nt":
        return {}

    creationflags = 0
    for flag_name in (
        "CREATE_NO_WINDOW",
        "CREATE_BREAKAWAY_FROM_JOB",
        "DETACHED_PROCESS",
        "CREATE_NEW_PROCESS_GROUP",
    ):
        creationflags |= int(getattr(subprocess, flag_name, 0) or 0)

    kwargs = build_windows_background_popen_kwargs()
    if creationflags:
        kwargs["creationflags"] = creationflags
    return kwargs


def resolve_background_python_executable(python_executable: str | Path) -> Path:
    executable_path = Path(str(python_executable)).resolve()
    if os.name == "nt" and executable_path.name.casefold() == "python.exe":
        pythonw_path = executable_path.with_name("pythonw.exe")
        if pythonw_path.exists():
            return pythonw_path.resolve()
    return executable_path


def spawn_background_process(
    command_argv: list[str | Path],
    *,
    cwd: str | Path,
    stdout_path: str | Path | None = None,
    stderr_path: str | Path | None = None,
    detached_from_parent_job: bool = False,
) -> int:
    if not command_argv:
        raise RuntimeError("background command argv is empty")

    resolved_cwd = Path(str(cwd)).resolve()
    resolved_stdout = Path(str(stdout_path)).resolve() if stdout_path else None
    resolved_stderr = Path(str(stderr_path)).resolve() if stderr_path else None
    if resolved_stdout is not None:
        resolved_stdout.parent.mkdir(parents=True, exist_ok=True)
    if resolved_stderr is not None:
        resolved_stderr.parent.mkdir(parents=True, exist_ok=True)

    normalized_argv = [str(item) for item in command_argv]
    if os.name == "nt":
        executable_path = Path(normalized_argv[0])
        if executable_path.name.casefold() in {"python.exe", "pythonw.exe"}:
            normalized_argv[0] = str(resolve_background_python_executable(executable_path))

    stdout_handle = resolved_stdout.open("wb") if resolved_stdout is not None else subprocess.DEVNULL
    stderr_handle = resolved_stderr.open("wb") if resolved_stderr is not None else subprocess.DEVNULL
    try:
        process = subprocess.Popen(
            normalized_argv,
            cwd=str(resolved_cwd),
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            close_fds=True,
            **(
                build_windows_detached_popen_kwargs()
                if detached_from_parent_job
                else build_windows_background_popen_kwargs()
            ),
        )
    except OSError as exc:
        raise RuntimeError(f"failed to start background process: {exc}") from exc
    finally:
        if resolved_stdout is not None:
            stdout_handle.close()
        if resolved_stderr is not None:
            stderr_handle.close()
    return int(process.pid)


def wait_for_process_alive(pid: int, *, timeout_seconds: float = 2.0, interval_seconds: float = 0.1) -> bool:
    deadline = time.time() + max(float(timeout_seconds), 0.0)
    while time.time() < deadline:
        if is_process_alive(pid):
            return True
        time.sleep(max(float(interval_seconds), 0.01))
    return is_process_alive(pid)


def find_tcp_listening_pid(port: int) -> int:
    if int(port or 0) <= 0:
        return 0
    if os.name != "nt":
        return 0
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return 0
    target_suffix = f":{int(port)}"
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        local_address = parts[1]
        state = parts[3].upper()
        pid_text = parts[4]
        if state != "LISTENING" or not local_address.endswith(target_suffix):
            continue
        try:
            return int(pid_text)
        except ValueError:
            return 0
    return 0


def terminate_process_tree(pid: int) -> bool:
    try:
        normalized_pid = int(pid)
    except (TypeError, ValueError):
        return False
    if normalized_pid <= 0:
        return False
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(normalized_pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    try:
        os.kill(normalized_pid, 15)
    except OSError:
        return False
    return True


def terminate_process(pid: int) -> bool:
    try:
        normalized_pid = int(pid)
    except (TypeError, ValueError):
        return False
    if normalized_pid <= 0:
        return False
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(normalized_pid), "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    try:
        os.kill(normalized_pid, 15)
    except OSError:
        return False
    return True


def _is_process_alive_windows_tasklist(pid: int) -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return False
    output = (result.stdout or "").strip()
    if not output or "No tasks are running" in output:
        return False
    return str(int(pid)) in output


def _is_process_alive_windows_openprocess(pid: int) -> bool:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    ERROR_ACCESS_DENIED = 5
    ERROR_INVALID_PARAMETER = 87

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        error_code = int(ctypes.get_last_error() or 0)
        if error_code == ERROR_ACCESS_DENIED:
            return True
        if error_code == ERROR_INVALID_PARAMETER:
            return False
        return _is_process_alive_windows_tasklist(pid)

    try:
        exit_code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return _is_process_alive_windows_tasklist(pid)
        return int(exit_code.value) == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def is_process_alive(pid: int) -> bool:
    try:
        normalized_pid = int(pid)
    except (TypeError, ValueError):
        return False
    if normalized_pid <= 0:
        return False
    if os.name == "nt":
        return _is_process_alive_windows_openprocess(normalized_pid)
    try:
        os.kill(normalized_pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    except SystemError:
        return False
    return True
