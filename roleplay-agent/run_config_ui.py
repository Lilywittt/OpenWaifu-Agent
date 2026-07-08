from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from roleplay_agent.config import load_app_config
from roleplay_agent.config_ui.server import run_config_ui


def configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    app_config = load_app_config(PROJECT_DIR)
    ui_config = app_config.get("configUi", {}) if isinstance(app_config.get("configUi", {}), dict) else {}
    parser = argparse.ArgumentParser(description="Run the roleplay agent configuration UI.")
    parser.add_argument("--host", default=str(ui_config.get("host", "127.0.0.1")))
    parser.add_argument("--port", type=int, default=int(ui_config.get("port", 8781)))
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    run_config_ui(PROJECT_DIR, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
