from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from publish.browser_profiles import (
    cleanup_edge_publish_sessions,
    read_edge_publish_profile_status,
    sync_edge_publish_profile,
)


def configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect or sync browser profiles used by the publish service.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("status")
    subparsers.add_parser("sync-edge")
    subparsers.add_parser("cleanup-sessions")
    return parser


def _show_status() -> int:
    payload = {
        "edge": read_edge_publish_profile_status(PROJECT_DIR),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0


def _sync_edge() -> int:
    try:
        payload = sync_edge_publish_profile(PROJECT_DIR)
    except Exception as exc:
        print(f"[publish-browser] {exc}", flush=True)
        return 1
    print("[publish-browser] Edge 发布配置已同步。", flush=True)
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0


def _cleanup_sessions() -> int:
    payload = cleanup_edge_publish_sessions(PROJECT_DIR)
    print("[publish-browser] Edge 发布会话目录已清理。", flush=True)
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    if args.action == "status":
        return _show_status()
    if args.action == "sync-edge":
        return _sync_edge()
    if args.action == "cleanup-sessions":
        return _cleanup_sessions()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
