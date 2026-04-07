from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from io_utils import ensure_dir, read_json, write_json
from runtime_layout import RunBundle, sanitize_segment


def configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def batch_root(batch_kind: str) -> Path:
    return PROJECT_DIR / "runtime" / "test_batches" / batch_kind


def build_batch_dir(batch_kind: str, label: str) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    return batch_root(batch_kind) / f"{stamp}_{sanitize_segment(label)}"


def create_sample_bundle(sample_root: Path, sample_id: int) -> RunBundle:
    creative_dir = sample_root / "creative"
    prompt_builder_dir = sample_root / "prompt_builder"
    execution_dir = sample_root / "execution"
    output_dir = sample_root / "output"
    trace_dir = sample_root / "trace"
    for path in (sample_root, creative_dir, prompt_builder_dir, execution_dir, output_dir, trace_dir):
        ensure_dir(path)
    bundle = RunBundle(
        run_id=f"{sample_root.parent.name}_sample{sample_id:02d}",
        root=sample_root,
        input_dir=sample_root / "input",
        creative_dir=creative_dir,
        prompt_builder_dir=prompt_builder_dir,
        execution_dir=execution_dir,
        output_dir=output_dir,
        trace_dir=trace_dir,
    )
    ensure_dir(bundle.input_dir)
    write_json(bundle.root / "bundle.json", bundle.to_dict())
    return bundle


def latest_world_design_batch() -> Path:
    root = batch_root("world_design")
    candidates = sorted([path for path in root.iterdir() if path.is_dir()], key=lambda path: path.name)
    if not candidates:
        raise RuntimeError("No world_design batch directory exists yet.")
    return candidates[-1]


def resolve_scene_draft_paths(*, scene_files: list[str], source_batch: str, count: int) -> list[Path]:
    if scene_files:
        paths = [Path(path).resolve() for path in scene_files]
    else:
        batch_dir = Path(source_batch).resolve() if source_batch else latest_world_design_batch()
        paths = sorted((batch_dir / "samples").glob("*/creative/01_world_design.json"), key=lambda path: path.as_posix())
    if count <= 0:
        raise RuntimeError("count must be greater than 0")
    if len(paths) < count:
        raise RuntimeError(f"Requested {count} scene drafts but only found {len(paths)}.")
    return paths[:count]


def read_stage_json(path: Path) -> dict:
    return read_json(path)
