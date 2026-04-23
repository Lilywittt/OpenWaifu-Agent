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
        self.assertIn("/api/toggle-favorite", html)
        self.assertIn("preview-image", html)
        self.assertIn("recent-runs", html)
        self.assertIn("events", html)

    def test_render_run_detail_html_contains_detail_panel_elements(self):
        html = render_run_detail_html(
            project_name="单小伊 Agent 运维面板",
            run_id="2026-04-11T18-30-00_demo",
            refresh_seconds=5,
        )

        self.assertIn("/api/run-detail?runId=", html)
        self.assertIn('id="favorite-btn"', html)
        self.assertIn("/api/toggle-favorite", html)
        self.assertIn(".preview-path", html)
        self.assertIn("data.generatedImagePath", html)
        self.assertIn("section-nav-links", html)
        self.assertIn("details[data-raw-key]", html)
        self.assertIn("expandedRawKeys", html)


if __name__ == "__main__":
    unittest.main()
