from __future__ import annotations

from .views import render_content_workbench_html


def render_content_workbench_lab_html(*, project_name: str, refresh_seconds: int) -> str:
    title = f"{project_name} - 前端实验"
    return render_content_workbench_html(project_name=title, refresh_seconds=refresh_seconds)
