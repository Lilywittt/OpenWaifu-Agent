from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from tools.publishing.smoke_publish import run_publish_smoke, summarize_publish_smoke


def configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run no-submit browser publishing smoke checks.")
    parser.add_argument("--run-id", default="latest", help="Run id to publish from. Defaults to latest publishable run.")
    parser.add_argument("--targets", nargs="*", default=[], help="Target ids to check. Defaults to all browser publish targets.")
    parser.add_argument("--allow-submit", action="store_true", help="Allow adapters to use their configured autoSubmit value.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    parser.add_argument("--fail-on-error", action="store_true", help="Return exit code 1 if any target fails.")
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    report = run_publish_smoke(
        PROJECT_DIR,
        run_id=args.run_id,
        target_ids=args.targets or None,
        allow_submit=args.allow_submit,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    else:
        print(summarize_publish_smoke(report), flush=True)
    failed_count = int(report.get("meta", {}).get("failedCount", 0) or 0)
    return 1 if args.fail_on_error and failed_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
