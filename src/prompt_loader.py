from __future__ import annotations

from pathlib import Path


def load_prompt_text(project_dir: Path, relative_path: str) -> str:
    prompt_path = project_dir / relative_path
    return prompt_path.read_text(encoding="utf-8-sig").strip()
