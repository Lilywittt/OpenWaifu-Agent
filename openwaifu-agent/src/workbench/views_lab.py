from __future__ import annotations

from .views import render_content_workbench_html


def render_content_workbench_lab_html(*, project_name: str, refresh_seconds: int) -> str:
    html = render_content_workbench_html(
        project_name=f"{project_name} - Frontend Lab",
        refresh_seconds=refresh_seconds,
    )
    return html.replace(
        '<body data-workbench-view="split-scroll">',
        '<body data-workbench-view="split-scroll" data-lab-view="split-scroll">',
        1,
    )
