from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ops.dashboard_views import render_dashboard_html, render_run_detail_html


class OpsDashboardViewsTests(unittest.TestCase):
    def test_render_dashboard_html_contains_core_panel_elements(self):
        html = render_dashboard_html(project_name="单小伊 Agent 运维面板", refresh_seconds=5)

        self.assertIn("单小伊 Agent 运维面板", html)
        self.assertIn('id="hero-title"', html)
        self.assertIn("/api/snapshot", html)
        self.assertIn("preview-image", html)
        self.assertIn("待处理队列", html)
        self.assertIn("事件流", html)

    def test_render_run_detail_html_contains_detail_panel_elements(self):
        html = render_run_detail_html(
            project_name="单小伊 Agent 运维面板",
            run_id="2026-04-11T18-30-00_demo",
            refresh_seconds=5,
        )

        self.assertIn("最终送给生图基座的 Prompt", html)
        self.assertIn("/api/run-detail?runId=", html)
        self.assertIn("快速定位", html)
        self.assertIn("section-nav-links", html)
        self.assertIn("内容链概览", html)
        self.assertIn("details[data-raw-key]", html)
        self.assertIn("expandedRawKeys", html)


if __name__ == "__main__":
    unittest.main()
