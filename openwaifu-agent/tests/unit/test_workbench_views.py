from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.views import render_content_workbench_html


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


if __name__ == "__main__":
    unittest.main()
