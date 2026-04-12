from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from studio.content_workbench_views import render_content_workbench_html


class ContentWorkbenchViewsTests(unittest.TestCase):
    def test_render_workbench_html_contains_core_elements(self):
        html = render_content_workbench_html(project_name="单小伊 Agent 内容测试工作台", refresh_seconds=5)

        self.assertIn("单小伊 Agent 内容测试工作台", html)
        self.assertIn('id="source-kind"', html)
        self.assertIn('id="end-stage"', html)
        self.assertIn('id="source-content"', html)
        self.assertIn('id="creative-world-scene"', html)
        self.assertIn('id="prompt-positive"', html)
        self.assertIn("/api/start", html)
        self.assertIn("/api/stop", html)
        self.assertIn('id="history-list"', html)
        self.assertIn('id="history-filter-active"', html)
        self.assertIn('id="detail-actions"', html)
        self.assertIn("function shouldRenderDetail", html)
        self.assertIn("detailSuspendUntil", html)
        self.assertIn("function renderCompareBlocks", html)
        self.assertIn(".diff-token.changed.after", html)
        self.assertIn("查看原始文件内容", html)
        self.assertIn("ArrowDown", html)
        self.assertNotIn('id="detail-notice"', html)
        self.assertNotIn("错误：-", html)


if __name__ == "__main__":
    unittest.main()
