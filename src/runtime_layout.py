from __future__ import annotations

import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from io_utils import ensure_dir, write_json


def sanitize_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    return cleaned.strip("_") or "run"


@dataclass
class RunBundle:
    run_id: str
    root: Path
    input_dir: Path
    creative_dir: Path
    prompt_builder_dir: Path
    execution_dir: Path
    output_dir: Path
    trace_dir: Path

    def to_dict(self) -> dict:
        data = asdict(self)
        return {key: str(value) if isinstance(value, Path) else value for key, value in data.items()}


def runtime_root(project_dir: Path) -> Path:
    return project_dir / "runtime"


def runs_root(project_dir: Path) -> Path:
    return runtime_root(project_dir) / "runs"


def build_run_id(mode: str, label: str = "") -> str:
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    suffix = sanitize_segment(label or mode)
    return f"{stamp}_{suffix}"


def create_run_bundle(project_dir: Path, mode: str, label: str = "") -> RunBundle:
    run_id = build_run_id(mode, label)
    root = runs_root(project_dir) / run_id
    bundle = RunBundle(
        run_id=run_id,
        root=root,
        input_dir=root / "input",
        creative_dir=root / "creative",
        prompt_builder_dir=root / "prompt_builder",
        execution_dir=root / "execution",
        output_dir=root / "output",
        trace_dir=root / "trace",
    )
    ensure_dir(bundle.input_dir)
    ensure_dir(bundle.creative_dir)
    ensure_dir(bundle.prompt_builder_dir)
    ensure_dir(bundle.execution_dir)
    ensure_dir(bundle.output_dir)
    ensure_dir(bundle.trace_dir)
    write_json(bundle.root / "bundle.json", bundle.to_dict())
    return bundle


def update_latest(project_dir: Path, bundle: RunBundle, summary: dict) -> Path:
    latest_path = runtime_root(project_dir) / "latest.json"
    payload = {
        "runId": bundle.run_id,
        "runRoot": str(bundle.root),
        "outputDir": str(bundle.output_dir),
        "summary": summary,
    }
    write_json(latest_path, payload)
    return latest_path


def delete_run_bundle(bundle: RunBundle) -> None:
    if bundle.root.exists():
        shutil.rmtree(bundle.root, ignore_errors=True)
