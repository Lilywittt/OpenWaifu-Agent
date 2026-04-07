from __future__ import annotations

import re
from pathlib import Path


def load_prompt_text(project_dir: Path, relative_path: str) -> str:
    prompt_path = project_dir / relative_path
    return prompt_path.read_text(encoding="utf-8-sig").strip()


def render_prompt_text(project_dir: Path, relative_path: str, replacements: dict[str, str]) -> str:
    prompt_text = load_prompt_text(project_dir, relative_path)
    rendered = prompt_text
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))

    missing = sorted(set(re.findall(r"\{\{([A-Za-z0-9_]+)\}\}", rendered)))
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"Prompt template still contains unresolved placeholders: {joined}")
    return rendered
