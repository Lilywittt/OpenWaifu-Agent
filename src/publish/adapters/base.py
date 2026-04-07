from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class PublishAdapter(Protocol):
    def __call__(
        self,
        *,
        project_dir: Path,
        bundle,
        target_id: str,
        target_config: dict[str, Any],
        publish_input: dict[str, Any],
    ) -> dict[str, Any]:
        ...
