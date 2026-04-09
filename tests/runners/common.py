from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Callable


PROJECT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from io_utils import ensure_dir, write_json
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
    social_post_dir = sample_root / "social_post"
    prompt_builder_dir = sample_root / "prompt_builder"
    execution_dir = sample_root / "execution"
    publish_dir = sample_root / "publish"
    output_dir = sample_root / "output"
    trace_dir = sample_root / "trace"
    for path in (sample_root, creative_dir, social_post_dir, prompt_builder_dir, execution_dir, publish_dir, output_dir, trace_dir):
        ensure_dir(path)
    bundle = RunBundle(
        run_id=f"{sample_root.parent.name}_sample{sample_id:02d}",
        root=sample_root,
        input_dir=sample_root / "input",
        creative_dir=creative_dir,
        social_post_dir=social_post_dir,
        prompt_builder_dir=prompt_builder_dir,
        execution_dir=execution_dir,
        publish_dir=publish_dir,
        output_dir=output_dir,
        trace_dir=trace_dir,
    )
    ensure_dir(bundle.input_dir)
    write_json(bundle.root / "bundle.json", bundle.to_dict())
    return bundle


def latest_run_dirs() -> list[Path]:
    root = PROJECT_DIR / "runtime" / "runs"
    if not root.exists():
        return []
    return sorted([path for path in root.iterdir() if path.is_dir()], key=lambda path: path.name, reverse=True)


def latest_creative_package_paths(count: int) -> list[Path]:
    if count <= 0:
        raise RuntimeError("count must be greater than 0")
    resolved: list[Path] = []
    for run_dir in latest_run_dirs():
        candidate = run_dir / "creative" / "05_creative_package.json"
        if candidate.exists():
            resolved.append(candidate.resolve())
        if len(resolved) >= count:
            return resolved
    raise RuntimeError(f"Requested {count} creative packages but only found {len(resolved)} in recent runs.")


def latest_world_design_input_paths(count: int) -> list[Path]:
    if count <= 0:
        raise RuntimeError("count must be greater than 0")
    resolved: list[Path] = []
    for run_dir in latest_run_dirs():
        candidate = run_dir / "creative" / "01_world_design_input.json"
        if candidate.exists():
            resolved.append(candidate.resolve())
        if len(resolved) >= count:
            return resolved
    raise RuntimeError(f"Requested {count} world design inputs but only found {len(resolved)} in recent runs.")


def latest_scene_draft_paths(count: int) -> list[Path]:
    if count <= 0:
        raise RuntimeError("count must be greater than 0")
    resolved: list[Path] = []
    for run_dir in latest_run_dirs():
        candidate = run_dir / "creative" / "01_world_design.json"
        if candidate.exists():
            resolved.append(candidate.resolve())
        if len(resolved) >= count:
            return resolved
    raise RuntimeError(f"Requested {count} scene drafts but only found {len(resolved)} in recent runs.")


def _resolve_stage_file_from_source(
    source: str,
    *,
    expected_filename: str,
    relative_candidates: list[str],
) -> Path:
    path = Path(source).resolve()
    if path.is_file():
        if path.name != expected_filename:
            raise RuntimeError(f"Unsupported source file: {path}")
        return path
    for relative_path in relative_candidates:
        candidate = path / relative_path
        if candidate.exists():
            return candidate.resolve()
    raise RuntimeError(f"Could not find {expected_filename} under source: {path}")


def resolve_source_path_to_creative_package(source: str) -> Path:
    return _resolve_stage_file_from_source(
        source,
        expected_filename="05_creative_package.json",
        relative_candidates=[
            "creative/05_creative_package.json",
            "05_creative_package.json",
        ],
    )


def resolve_source_path_to_world_design_input(source: str) -> Path:
    return _resolve_stage_file_from_source(
        source,
        expected_filename="01_world_design_input.json",
        relative_candidates=[
            "creative/01_world_design_input.json",
            "01_world_design_input.json",
        ],
    )


def resolve_source_path_to_scene_draft(source: str) -> Path:
    return _resolve_stage_file_from_source(
        source,
        expected_filename="01_world_design.json",
        relative_candidates=[
            "creative/01_world_design.json",
            "01_world_design.json",
        ],
    )


def _resolve_stage_paths(
    *,
    sources: list[str],
    source_batch: str,
    count: int,
    resolve_source: Callable[[str], Path],
    batch_pattern: str,
    default_paths: Callable[[int], list[Path]] | None = None,
) -> list[Path]:
    if count <= 0:
        raise RuntimeError("count must be greater than 0")

    resolved: list[Path] = []
    seen: set[str] = set()

    for source in sources:
        stage_path = resolve_source(source)
        key = str(stage_path).lower()
        if key not in seen:
            seen.add(key)
            resolved.append(stage_path)

    if source_batch:
        batch_dir = Path(source_batch).resolve()
        batch_paths = sorted(
            (batch_dir / "samples").glob(batch_pattern),
            key=lambda item: item.as_posix(),
        )
        for stage_path in batch_paths:
            stage_path = stage_path.resolve()
            key = str(stage_path).lower()
            if key not in seen:
                seen.add(key)
                resolved.append(stage_path)

    if not resolved and default_paths is not None:
        return default_paths(count)
    if not resolved:
        raise RuntimeError("No sources were provided.")
    if len(resolved) < count:
        raise RuntimeError(f"Requested {count} sources but only found {len(resolved)}.")
    return resolved[:count]


def resolve_creative_package_paths(*, sources: list[str], source_batch: str, count: int) -> list[Path]:
    return _resolve_stage_paths(
        sources=sources,
        source_batch=source_batch,
        count=count,
        resolve_source=resolve_source_path_to_creative_package,
        batch_pattern="*/creative/05_creative_package.json",
        default_paths=None,
    )


def resolve_world_design_input_paths(*, sources: list[str], source_batch: str, count: int) -> list[Path]:
    return _resolve_stage_paths(
        sources=sources,
        source_batch=source_batch,
        count=count,
        resolve_source=resolve_source_path_to_world_design_input,
        batch_pattern="*/creative/01_world_design_input.json",
        default_paths=latest_world_design_input_paths,
    )


def resolve_scene_draft_paths(*, sources: list[str], source_batch: str, count: int) -> list[Path]:
    return _resolve_stage_paths(
        sources=sources,
        source_batch=source_batch,
        count=count,
        resolve_source=resolve_source_path_to_scene_draft,
        batch_pattern="*/creative/01_world_design.json",
        default_paths=latest_scene_draft_paths,
    )
