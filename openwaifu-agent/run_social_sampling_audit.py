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

from tools.social_sampling.audit_sources import (
    audit_social_sampling_sources,
    summarize_social_sampling_audit,
)


def configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit all registered social sampling sources.")
    parser.add_argument(
        "--only",
        nargs="*",
        default=[],
        help="Audit only matching source/provider keys or display names.",
    )
    parser.add_argument(
        "--no-candidates",
        action="store_true",
        help="Store only previews instead of full candidate lists.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full JSON report.",
    )
    parser.add_argument(
        "--fail-on-unavailable",
        action="store_true",
        help="Return exit code 1 if any registered source cannot provide enough candidates.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    report = audit_social_sampling_sources(
        PROJECT_DIR,
        only=args.only,
        include_candidates=not args.no_candidates,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    else:
        print(summarize_social_sampling_audit(report), flush=True)
    if args.fail_on_unavailable and int(report.get("meta", {}).get("failedCount", 0) or 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
