from __future__ import annotations

"""独立验证 QQ bot 文本消息发送的测试脚本，不接生产发布层。"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
TOOLS_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
for import_path in (TOOLS_DIR, SRC_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from common import build_batch_dir, configure_utf8_stdio

from io_utils import ensure_dir, write_json, write_text
from publish.qq_bot_client import (
    fetch_app_access_token,
    load_qq_bot_message_config,
    resolve_qq_bot_credentials,
    send_text_message,
)


BATCH_KIND = "qq_bot_message"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send one standalone QQ bot text message for smoke testing.")
    parser.add_argument("--content", required=True)
    parser.add_argument("--label", default="qq_bot_message")
    parser.add_argument("--config", default=str(PROJECT_DIR / "config" / "publish" / "qq_bot_message.json"))
    parser.add_argument("--scene", choices=["group", "user"], default="")
    parser.add_argument("--target-openid", default="")
    return parser


def run_once(*, content: str, label: str, config_path: str, scene: str, target_openid: str) -> Path:
    batch_dir = build_batch_dir(BATCH_KIND, label)
    ensure_dir(batch_dir)
    try:
        config = load_qq_bot_message_config(PROJECT_DIR, Path(config_path).resolve())
        credentials = resolve_qq_bot_credentials(
            PROJECT_DIR,
            config,
            scene_override=scene,
            target_openid_override=target_openid,
        )
        token_response = fetch_app_access_token(
            app_id=credentials["appId"],
            app_secret=credentials["appSecret"],
            access_token_url=credentials["accessTokenUrl"],
            timeout_ms=credentials["timeoutMs"],
        )
        message_response = send_text_message(
            access_token=str(token_response["access_token"]),
            api_base_url=credentials["apiBaseUrl"],
            scene=credentials["scene"],
            target_openid=credentials["targetOpenId"],
            content=content,
            timeout_ms=credentials["timeoutMs"],
        )

        write_json(
            batch_dir / "00_runner_input.json",
            {
                "content": content,
                "configPath": str(Path(config_path).resolve()),
                "scene": credentials["scene"],
                "targetOpenId": credentials["targetOpenId"],
            },
        )
        write_json(
            batch_dir / "01_access_token_request.json",
            {
                "url": credentials["accessTokenUrl"],
                "appId": credentials["appId"],
                "timeoutMs": credentials["timeoutMs"],
            },
        )
        write_json(
            batch_dir / "02_access_token_response.json",
            {
                "expiresIn": token_response.get("expires_in"),
            },
        )
        write_json(
            batch_dir / "03_message_request.json",
            {
                "url": message_response.get("_request", {}).get("url", ""),
                "payload": message_response.get("_request", {}).get("payload", {}),
            },
        )
        sanitized_response = dict(message_response)
        sanitized_response.pop("_request", None)
        write_json(batch_dir / "04_message_response.json", sanitized_response)
        write_text(
            batch_dir / "complete_results.md",
            "\n".join(
                [
                    "# QQ bot 文本消息测试结果",
                    "",
                    f"- 批次目录: `{batch_dir}`",
                    f"- 场景: `{credentials['scene']}`",
                    f"- 目标 openid: `{credentials['targetOpenId']}`",
                    "",
                    "## 文本内容",
                    "```text",
                    content.strip(),
                    "```",
                    "",
                    "## 消息响应",
                    "```json",
                    json.dumps(sanitized_response, ensure_ascii=False, indent=2),
                    "```",
                ]
            ),
        )
        return batch_dir
    except Exception:
        shutil.rmtree(batch_dir, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    batch_dir = run_once(
        content=args.content,
        label=args.label,
        config_path=args.config,
        scene=args.scene,
        target_openid=args.target_openid,
    )
    print(batch_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
