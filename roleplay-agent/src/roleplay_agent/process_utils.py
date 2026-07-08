from __future__ import annotations

import ctypes
import os
import subprocess
from pathlib import Path
from typing import Any


def build_windows_background_popen_kwargs() -> dict[str, Any]:
    if os.name != "nt":
        return {}
    creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0) or 0)
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
    for flag_name in ("CREATE_NO_WINDOW", "CREATE_BREAKAWAY_FROM_JOB", "DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP"):
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
    stdout_path: str | Path,
    stderr_path: str | Path,
    detached_from_parent_job: bool = True,
) -> int:
    if not command_argv:
        raise RuntimeError("background command argv is empty.")
    resolved_cwd = Path(str(cwd)).resolve()
    resolved_stdout = Path(str(stdout_path)).resolve()
    resolved_stderr = Path(str(stderr_path)).resolve()
    resolved_stdout.parent.mkdir(parents=True, exist_ok=True)
    resolved_stderr.parent.mkdir(parents=True, exist_ok=True)
    argv = [str(item) for item in command_argv]
    if os.name == "nt":
        exe = Path(argv[0])
        if exe.name.casefold() in {"python.exe", "pythonw.exe"}:
            argv[0] = str(resolve_background_python_executable(exe))
    with resolved_stdout.open("wb") as stdout_handle, resolved_stderr.open("wb") as stderr_handle:
        process = subprocess.Popen(
            argv,
            cwd=str(resolved_cwd),
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            close_fds=True,
            **(build_windows_detached_popen_kwargs() if detached_from_parent_job else build_windows_background_popen_kwargs()),
        )
    return int(process.pid)


def is_process_alive(pid: int) -> bool:
    try:
        normalized_pid = int(pid)
    except (TypeError, ValueError):
        return False
    if normalized_pid <= 0:
        return False
    if os.name == "nt":
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            process_query_limited_information = 0x1000
            still_active = 259
            handle = kernel32.OpenProcess(process_query_limited_information, False, normalized_pid)
            if not handle:
                return False
            try:
                exit_code = ctypes.c_ulong()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return False
                return int(exit_code.value) == still_active
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(normalized_pid, 0)
    except PermissionError:
        return True
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
