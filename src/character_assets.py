from __future__ import annotations

from pathlib import Path

from io_utils import read_json


def load_character_assets(project_dir: Path) -> dict:
    character_dir = project_dir / "character" / "editable"
    return {
        "subjectProfile": read_json(character_dir / "subject_profile.json"),
    }
