from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from runtime_layout import sanitize_segment


def configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def tool_run_root(kind: str) -> Path:
    return PROJECT_DIR / "runtime" / "tool_runs" / kind


def build_tool_run_dir(kind: str, label: str) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    return tool_run_root(kind) / f"{stamp}_{sanitize_segment(label)}"
