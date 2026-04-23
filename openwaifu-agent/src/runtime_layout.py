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
    social_post_dir: Path
    prompt_builder_dir: Path
    prompt_guard_dir: Path
    execution_dir: Path
    publish_dir: Path
    output_dir: Path
    trace_dir: Path

    def to_dict(self) -> dict:
        data = asdict(self)
        return {key: str(value) if isinstance(value, Path) else value for key, value in data.items()}


def build_run_bundle(root: Path, run_id: str) -> RunBundle:
    root = Path(root).resolve()
    return RunBundle(
        run_id=str(run_id),
        root=root,
        input_dir=root / "input",
        creative_dir=root / "creative",
        social_post_dir=root / "social_post",
        prompt_builder_dir=root / "prompt_builder",
        prompt_guard_dir=root / "prompt_guard",
        execution_dir=root / "execution",
        publish_dir=root / "publish",
        output_dir=root / "output",
        trace_dir=root / "trace",
    )


def initialize_run_bundle(bundle: RunBundle) -> RunBundle:
    ensure_dir(bundle.input_dir)
    ensure_dir(bundle.creative_dir)
    ensure_dir(bundle.social_post_dir)
    ensure_dir(bundle.prompt_builder_dir)
    ensure_dir(bundle.prompt_guard_dir)
    ensure_dir(bundle.execution_dir)
    ensure_dir(bundle.publish_dir)
    ensure_dir(bundle.output_dir)
    ensure_dir(bundle.trace_dir)
    write_json(bundle.root / "bundle.json", bundle.to_dict())
    return bundle


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
    return initialize_run_bundle(build_run_bundle(root, run_id))


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
