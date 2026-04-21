from __future__ import annotations

from pathlib import Path

from io_utils import normalize_spaces, read_json


CONFIG_PATH = Path("config") / "character_assets.json"
LEGACY_TOP_LEVEL_KEYS = {
    "schema_version",
    "profile_zh",
    "identity_truth",
    "face_truth",
    "hair_truth",
    "body_truth",
    "forbidden_changes_zh",
}


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


def _validate_subject_profile(payload: dict) -> None:
    legacy_keys = sorted(key for key in LEGACY_TOP_LEVEL_KEYS if key in payload)
    if legacy_keys:
        raise RuntimeError(
            "character subject profile uses legacy fields: " + ", ".join(legacy_keys)
        )

    subject_id = normalize_spaces(str(payload.get("subject_id", "")))
    if not subject_id:
        raise RuntimeError("character subject profile is missing subject_id.")

    display_name = normalize_spaces(str(payload.get("display_name_zh", "")))
    if not display_name:
        raise RuntimeError("character subject profile is missing display_name_zh.")

    for key in ("identity_zh", "appearance_zh", "psychology_zh"):
        value = payload.get(key)
        if not isinstance(value, list):
            raise RuntimeError(f"character subject profile must define {key} as a list.")
        if not any(normalize_spaces(str(item)) for item in value):
            raise RuntimeError(f"character subject profile has empty {key}.")

    for key in ("allowed_changes_zh", "forbidden_drift_zh"):
        value = payload.get(key)
        if not isinstance(value, list):
            raise RuntimeError(f"character subject profile must define {key} as a list.")
        if not any(normalize_spaces(str(item)) for item in value):
            raise RuntimeError(f"character subject profile has empty {key}.")

    notes = payload.get("notes_zh", [])
    if not isinstance(notes, list):
        raise RuntimeError("character subject profile must define notes_zh as a list.")


def load_character_assets(project_dir: Path) -> dict:
    config_path = project_dir / CONFIG_PATH
    if not config_path.is_file():
        raise RuntimeError(f"character assets config does not exist: {config_path}")

    config = read_json(config_path)
    subject_profile_path = _resolve_subject_profile_path(project_dir, config)
    subject_profile = read_json(subject_profile_path)
    _validate_subject_profile(subject_profile)
    return {
        "subjectProfile": subject_profile,
    }
