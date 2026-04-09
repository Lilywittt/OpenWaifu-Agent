from __future__ import annotations

"""独立验证 QQ bot 凭据并获取 access token 的测试脚本，不发送消息。"""

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
)


BATCH_KIND = "qq_bot_token"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify QQ bot credentials by fetching one app access token.")
    parser.add_argument("--label", default="qq_bot_token")
    parser.add_argument("--config", default=str(PROJECT_DIR / "config" / "publish" / "qq_bot_message.json"))
    parser.add_argument("--scene", choices=["group", "user"], default="group")
    return parser


def run_once(*, label: str, config_path: str, scene: str) -> Path:
    batch_dir = build_batch_dir(BATCH_KIND, label)
    ensure_dir(batch_dir)
    try:
        config = load_qq_bot_message_config(PROJECT_DIR, Path(config_path).resolve())
        credentials = resolve_qq_bot_credentials(
            PROJECT_DIR,
            config,
            scene_override=scene,
            target_openid_override="placeholder_openid",
        )
        token_response = fetch_app_access_token(
            app_id=credentials["appId"],
            app_secret=credentials["appSecret"],
            access_token_url=credentials["accessTokenUrl"],
            timeout_ms=credentials["timeoutMs"],
        )

        write_json(
            batch_dir / "00_runner_input.json",
            {
                "configPath": str(Path(config_path).resolve()),
                "scene": credentials["scene"],
                "accessTokenUrl": credentials["accessTokenUrl"],
                "timeoutMs": credentials["timeoutMs"],
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
                "hasAccessToken": bool(str(token_response.get("access_token", "")).strip()),
            },
        )
        write_text(
            batch_dir / "complete_results.md",
            "\n".join(
                [
                    "# QQ bot access token 验证结果",
                    "",
                    f"- 批次目录: `{batch_dir}`",
                    f"- 场景: `{credentials['scene']}`",
                    f"- access token URL: `{credentials['accessTokenUrl']}`",
                    "",
                    "## 响应摘要",
                    "```json",
                    json.dumps(
                        {
                            "expiresIn": token_response.get("expires_in"),
                            "hasAccessToken": bool(str(token_response.get("access_token", "")).strip()),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
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
        label=args.label,
        config_path=args.config,
        scene=args.scene,
    )
    print(batch_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
