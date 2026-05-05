from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.views import render_content_workbench_html
from workbench.views_lab import render_content_workbench_lab_html


class WorkbenchViewsTests(unittest.TestCase):
    def test_render_workbench_html_escapes_title_for_html_and_javascript(self):
        html = render_content_workbench_html(
            project_name='<img src=x onerror=1>"quoted"',
            refresh_seconds=5,
        )

        self.assertIn("&lt;img src=x onerror=1&gt;&quot;quoted&quot;", html)
        self.assertNotIn('<title><img src=x onerror=1>"quoted"</title>', html)
        self.assertNotIn('<h1 id="hero-title"><img src=x onerror=1>"quoted"</h1>', html)
        self.assertIn(
            'snapshot?.identity?.workbenchTitle || "<img src=x onerror=1>\\"quoted\\"";',
            html,
        )

    def test_render_workbench_html_contains_display_order_controls(self):
        html = render_content_workbench_html(
            project_name="OpenWaifu Agent",
            refresh_seconds=5,
        )

        self.assertIn('id="history-manage-toggle"', html)
        self.assertIn('id="history-manage-bar"', html)
        self.assertIn("/api/display-order/pin", html)
        self.assertIn("/api/display-order/reorder", html)
        self.assertIn("data-history-pin-toggle", html)
        self.assertIn("data-history-drag-item", html)
        self.assertIn('data-workbench-view="split-scroll"', html)
        self.assertIn('data-workbench-workspace', html)
        self.assertIn('setAttribute("data-workbench-pane", "left")', html)
        self.assertIn('setAttribute("data-workbench-pane", "right")', html)
        self.assertIn("__OPENWAIFU_WORKBENCH_SPLIT_READY__", html)

    def test_render_workbench_lab_html_wraps_production_view_with_split_scroll_experiment(self):
        html = render_content_workbench_lab_html(
            project_name="OpenWaifu Agent",
            refresh_seconds=5,
        )

        self.assertIn('data-lab-view="split-scroll"', html)
        self.assertIn('data-workbench-view="split-scroll"', html)
        self.assertIn('data-workbench-workspace', html)
        self.assertIn('setAttribute("data-workbench-pane", "left")', html)
        self.assertIn('setAttribute("data-workbench-pane", "right")', html)
        self.assertIn("body.workbench-split-root", html)
        self.assertIn("__OPENWAIFU_WORKBENCH_SPLIT_READY__", html)
        self.assertIn('id="history-manage-toggle"', html)


if __name__ == "__main__":
    unittest.main()
