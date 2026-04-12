from __future__ import annotations

"""启动 QQ bot 私聊事件接收器，抓取 user_openid 并回写本地环境。"""

import argparse
import re
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

from flask import Flask, jsonify, request

PROJECT_DIR = Path(__file__).resolve().parents[2]
TOOLS_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
for import_path in (TOOLS_DIR, SRC_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from common import configure_utf8_stdio

from io_utils import write_json, write_text
from publish.qq_bot_callback import (
    build_callback_verification_response,
    extract_user_openid,
    persist_user_openid,
    qq_bot_callback_state_root,
    save_callback_event,
)
from publish.qq_bot_client import (
    fetch_app_access_token,
    load_qq_bot_message_config,
    resolve_qq_bot_credentials,
    send_text_message,
)


URL_PATTERN = re.compile(r"https://[a-z0-9.-]+", re.IGNORECASE)
CLOUDFLARED_DOWNLOAD_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
)
DEFAULT_REPLY_CONTENT = "我已经收到你的私聊啦，openid 也记下来了。"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a local QQ bot C2C callback receiver and capture user_openid."
    )
    parser.add_argument("--config", default=str(PROJECT_DIR / "config" / "publish" / "qq_bot_message.json"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--path", default="/qq-bot/callback")
    parser.add_argument("--no-tunnel", action="store_true")
    parser.add_argument("--no-auto-reply", action="store_true")
    parser.add_argument("--reply-content", default=DEFAULT_REPLY_CONTENT)
    return parser


def _write_receiver_status(
    *,
    state_root: Path,
    local_url: str,
    callback_path: str,
    public_url: str = "",
    callback_url: str = "",
) -> None:
    write_text(
        state_root / "receiver_status.txt",
        "\n".join(
            [
                f"local_url={local_url}",
                f"public_url={public_url}",
                f"callback_url={callback_url}",
                f"callback_path={callback_path}",
            ]
        )
        + "\n",
    )


def _cloudflared_binary_path(state_root: Path) -> Path:
    return state_root / "bin" / "cloudflared.exe"


def _ensure_cloudflared_binary(state_root: Path) -> Path | None:
    binary_path = _cloudflared_binary_path(state_root)
    if binary_path.exists():
        return binary_path
    binary_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlretrieve(CLOUDFLARED_DOWNLOAD_URL, binary_path)
    except Exception:
        return None
    return binary_path if binary_path.exists() else None


def _start_cloudflared(
    *,
    host: str,
    port: int,
    callback_path: str,
    state_root: Path,
    local_url: str,
) -> tuple[subprocess.Popen[str] | None, dict[str, str]]:
    binary_path = _ensure_cloudflared_binary(state_root)
    if binary_path is None:
        return None, {"publicUrl": "", "callbackUrl": ""}

    info: dict[str, str] = {
        "publicUrl": "",
        "callbackUrl": "",
    }
    out_log = state_root / "cloudflared.out.log"
    err_log = state_root / "cloudflared.err.log"
    out_log.write_text("", encoding="utf-8")
    err_log.write_text("", encoding="utf-8")
    process = subprocess.Popen(
        [
            str(binary_path),
            "tunnel",
            "--ha-connections",
            "4",
            "--url",
            f"http://{host}:{port}",
        ],
        cwd=str(PROJECT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    def _reader(stream, log_path: Path) -> None:
        if stream is None:
            return
        for line in stream:
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(line)
            if not info["publicUrl"]:
                match = URL_PATTERN.search(line)
                if match and "trycloudflare.com" in match.group(0):
                    info["publicUrl"] = match.group(0).rstrip("/")
                    info["callbackUrl"] = f"{info['publicUrl']}{callback_path}"
                    print(f"[qq-c2c] callback URL: {info['callbackUrl']}", flush=True)
                    write_json(
                        state_root / "tunnel.json",
                        {
                            "provider": "cloudflared",
                            "publicUrl": info["publicUrl"],
                            "callbackUrl": info["callbackUrl"],
                            "stdoutLogPath": str(out_log),
                            "stderrLogPath": str(err_log),
                        },
                    )
                    _write_receiver_status(
                        state_root=state_root,
                        local_url=local_url,
                        callback_path=callback_path,
                        public_url=info["publicUrl"],
                        callback_url=info["callbackUrl"],
                    )

    threading.Thread(target=_reader, args=(process.stdout, out_log), daemon=True).start()
    threading.Thread(target=_reader, args=(process.stderr, err_log), daemon=True).start()
    return process, info


def _start_localtunnel(
    *,
    host: str,
    port: int,
    callback_path: str,
    state_root: Path,
    local_url: str,
) -> tuple[subprocess.Popen[str] | None, dict[str, str]]:
    info: dict[str, str] = {
        "publicUrl": "",
        "callbackUrl": "",
    }
    log_path = state_root / "localtunnel.log"
    log_path.write_text("", encoding="utf-8")
    process = subprocess.Popen(
        [
            "cmd",
            "/c",
            "npx",
            "--yes",
            "localtunnel",
            "--port",
            str(port),
            "--local-host",
            host,
        ],
        cwd=str(PROJECT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    def _reader() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(line)
            if not info["publicUrl"]:
                match = URL_PATTERN.search(line)
                if match:
                    info["publicUrl"] = match.group(0).rstrip("/")
                    info["callbackUrl"] = f"{info['publicUrl']}{callback_path}"
                    print(f"[qq-c2c] callback URL: {info['callbackUrl']}", flush=True)
                    write_json(
                        state_root / "tunnel.json",
                        {
                            "provider": "localtunnel",
                            "publicUrl": info["publicUrl"],
                            "callbackUrl": info["callbackUrl"],
                            "logPath": str(log_path),
                        },
                    )
                    _write_receiver_status(
                        state_root=state_root,
                        local_url=local_url,
                        callback_path=callback_path,
                        public_url=info["publicUrl"],
                        callback_url=info["callbackUrl"],
                    )

    threading.Thread(target=_reader, daemon=True).start()
    return process, info


def run_receiver(
    *,
    config_path: str,
    host: str,
    port: int,
    callback_path: str,
    use_tunnel: bool,
    auto_reply: bool,
    reply_content: str,
) -> int:
    state_root = qq_bot_callback_state_root(PROJECT_DIR)
    config = load_qq_bot_message_config(PROJECT_DIR, Path(config_path).resolve())
    credentials = resolve_qq_bot_credentials(
        PROJECT_DIR,
        config,
        scene_override="user",
        target_openid_override="placeholder_user_openid",
    )
    callback_path = "/" + callback_path.strip().lstrip("/")
    local_url = f"http://{host}:{port}{callback_path}"

    app = Flask(__name__)
    tunnel_process: subprocess.Popen[str] | None = None

    _write_receiver_status(
        state_root=state_root,
        local_url=local_url,
        callback_path=callback_path,
    )

    if use_tunnel:
        tunnel_process, _ = _start_cloudflared(
            host=host,
            port=port,
            callback_path=callback_path,
            state_root=state_root,
            local_url=local_url,
        )
        if tunnel_process is None:
            tunnel_process, _ = _start_localtunnel(
                host=host,
                port=port,
                callback_path=callback_path,
                state_root=state_root,
                local_url=local_url,
            )

    @app.post(callback_path)
    def qq_callback():
        raw_body = request.get_data(as_text=True)
        payload = request.get_json(silent=True) or {}
        headers = {key: value for key, value in request.headers.items()}
        event_path = save_callback_event(
            PROJECT_DIR,
            payload=payload,
            headers=headers,
            raw_body=raw_body,
            callback_path=callback_path,
        )

        if int(payload.get("op", 0) or 0) == 13:
            response_payload = build_callback_verification_response(
                app_secret=credentials["appSecret"],
                payload=payload,
            )
            print(f"[qq-c2c] callback verified: {event_path}", flush=True)
            return jsonify(response_payload)

        user_openid = extract_user_openid(payload)
        if user_openid:
            latest_path = persist_user_openid(PROJECT_DIR, user_openid=user_openid, event_path=event_path)
            print(f"[qq-c2c] captured user_openid: {user_openid}", flush=True)
            print(f"[qq-c2c] latest file: {latest_path}", flush=True)
            if auto_reply:
                token_response = fetch_app_access_token(
                    app_id=credentials["appId"],
                    app_secret=credentials["appSecret"],
                    access_token_url=credentials["accessTokenUrl"],
                    timeout_ms=credentials["timeoutMs"],
                )
                send_text_message(
                    access_token=str(token_response["access_token"]),
                    api_base_url=credentials["apiBaseUrl"],
                    scene="user",
                    target_openid=user_openid,
                    content=reply_content,
                    timeout_ms=credentials["timeoutMs"],
                )
                print("[qq-c2c] auto reply sent.", flush=True)

        return jsonify({"ok": True})

    print("[qq-c2c] 现在你只需要做两件事：", flush=True)
    print("[qq-c2c] 1. 在 QQ 机器人后台只勾 C2C_MESSAGE_CREATE", flush=True)
    if use_tunnel:
        print("[qq-c2c] 2. 等下面出现 callback URL 后，把它粘到请求地址里", flush=True)
    else:
        print(f"[qq-c2c] 2. 你的本地回调地址是：{local_url}", flush=True)
    print(f"[qq-c2c] local callback: {local_url}", flush=True)
    if use_tunnel:
        print("[qq-c2c] 正在申请公网 HTTPS 地址，请稍等...", flush=True)

    try:
        app.run(host=host, port=port, debug=False, use_reloader=False)
    finally:
        if tunnel_process is not None:
            tunnel_process.terminate()
            try:
                tunnel_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                tunnel_process.kill()
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    return run_receiver(
        config_path=args.config,
        host=args.host,
        port=args.port,
        callback_path=args.path,
        use_tunnel=not args.no_tunnel,
        auto_reply=not args.no_auto_reply,
        reply_content=args.reply_content,
    )


if __name__ == "__main__":
    raise SystemExit(main())
