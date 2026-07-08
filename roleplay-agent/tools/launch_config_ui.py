from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from roleplay_agent.config import load_app_config


def _configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _show_error(message: str) -> None:
    log_dir = PROJECT_DIR / "runtime" / "service_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "config_ui_launcher.error.log").write_text(message, encoding="utf-8")
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror("openwaifu roleplay agent 配置界面", message)
        root.destroy()
    except Exception:
        print(message, flush=True)


def _port_is_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=1.0):
            return True
    except OSError:
        return False


def _ui_is_ready(url: str) -> bool:
    try:
        with urlopen(url + "/api/config?userId=preview", timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and "character" in payload and "prompts" in payload


def _start_server() -> int:
    log_dir = PROJECT_DIR / "runtime" / "service_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / "config_ui.stdout.log"
    stderr_path = log_dir / "config_ui.stderr.log"
    executable = Path(sys.executable)
    if executable.name.casefold() == "pythonw.exe":
        python_exe = executable
    else:
        pythonw = executable.with_name("pythonw.exe")
        python_exe = pythonw if pythonw.exists() else executable
    stdout_handle = stdout_path.open("ab")
    stderr_handle = stderr_path.open("ab")
    try:
        process = subprocess.Popen(
            [str(python_exe), str(PROJECT_DIR / "run_config_ui.py")],
            cwd=str(PROJECT_DIR),
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    finally:
        stdout_handle.close()
        stderr_handle.close()
    return int(process.pid)


def main() -> int:
    _configure_utf8_stdio()
    app_config = load_app_config(PROJECT_DIR)
    ui_config = app_config.get("configUi", {}) if isinstance(app_config.get("configUi", {}), dict) else {}
    host = str(ui_config.get("host", "127.0.0.1"))
    port = int(ui_config.get("port", 8781))
    url = f"http://{host}:{port}"
    if not _port_is_open(host, port):
        _start_server()
    deadline = time.time() + 12.0
    while time.time() < deadline:
        if _ui_is_ready(url):
            webbrowser.open(url, new=2)
            return 0
        time.sleep(0.4)
    _show_error(f"配置界面启动失败。请查看日志：{PROJECT_DIR / 'runtime' / 'service_logs'}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
