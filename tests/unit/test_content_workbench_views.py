from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
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
        self.assertIn('id="history-load-more"', html)
        self.assertIn('id="detail-actions"', html)
        self.assertIn("function shouldRenderDetail", html)
        self.assertIn("detailSuspendUntil", html)
        self.assertIn("historyFilter", html)
        self.assertIn("historyLimit", html)
        self.assertIn("review-path-input", html)
        self.assertIn("review-path-btn", html)
        self.assertIn("function clearReviewedPathDetail", html)
        self.assertIn("function reviewPathDetail", html)
        self.assertIn("function renderCompareBlocks", html)
        self.assertIn(".diff-token.changed.after", html)
        self.assertIn("查看原始文件内容", html)
        self.assertIn("ArrowDown", html)
        self.assertNotIn("max-height: 840px", html)
        self.assertNotIn("max-height: 320px", html)
        self.assertNotIn('id="detail-notice"', html)
        self.assertNotIn("错误：-", html)

    def test_rendered_workbench_script_is_valid_javascript(self):
        node_path = shutil.which("node")
        if not node_path:
            self.skipTest("node is not available")

        html = render_content_workbench_html(project_name="单小伊 Agent 内容测试工作台", refresh_seconds=5)
        script_start = html.index("<script>") + len("<script>")
        script_end = html.index("</script>", script_start)
        script = html[script_start:script_end]

        with TemporaryDirectory() as temp_dir:
            script_path = Path(temp_dir) / "content_workbench_script.js"
            script_path.write_text(script, encoding="utf-8")
            completed = subprocess.run(
                [node_path, "--check", str(script_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"rendered workbench script failed syntax check:\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
