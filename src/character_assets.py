from __future__ import annotations

from pathlib import Path

from io_utils import read_json


CONFIG_PATH = Path("config") / "character_assets.json"


def _resolve_subject_profile_path(project_dir: Path, config: dict) -> Path:
    raw_path = str(config.get("subjectProfilePath", "")).strip()
    if not raw_path:
        raise RuntimeError(f"{CONFIG_PATH.as_posix()} is missing subjectProfilePath.")

    subject_profile_path = Path(raw_path)
    if not subject_profile_path.is_absolute():
        subject_profile_path = project_dir / subject_profile_path

    if not subject_profile_path.is_file():
        raise RuntimeError(f"character subject profile does not exist: {subject_profile_path}")
    return subject_profile_path


def load_character_assets(project_dir: Path) -> dict:
    config_path = project_dir / CONFIG_PATH
    if not config_path.is_file():
        raise RuntimeError(f"character assets config does not exist: {config_path}")

    config = read_json(config_path)
    subject_profile_path = _resolve_subject_profile_path(project_dir, config)
    return {
        "subjectProfile": read_json(subject_profile_path),
    }
