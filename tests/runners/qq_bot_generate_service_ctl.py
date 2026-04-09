from __future__ import annotations

"""统一管理 QQ 私聊生成服务，支持 start / status / stop / restart。"""

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
TOOLS_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
for import_path in (TOOLS_DIR, SRC_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from common import configure_utf8_stdio

import start_qq_bot_generate_service as start_service
import status_qq_bot_generate_service as status_service
import stop_qq_bot_generate_service as stop_service


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Control the QQ private-chat generate service.")
    parser.add_argument("action", choices=["start", "status", "stop", "restart"])
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    if args.action == "start":
        return start_service.main()
    if args.action == "status":
        return status_service.main()
    if args.action == "stop":
        return stop_service.main()
    if args.action == "restart":
        stop_result = stop_service.main()
        if stop_result not in (0,):
            return stop_result
        return start_service.main()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
