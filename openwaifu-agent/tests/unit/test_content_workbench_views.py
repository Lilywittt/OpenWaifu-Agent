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
        self.assertIn("发起任务", html)
        self.assertIn("任务起点", html)
        self.assertIn("任务终点", html)
        self.assertIn("开始运行", html)
        self.assertIn("停止当前任务", html)
        self.assertIn("最近任务", html)
        self.assertIn("未选择任务", html)
        self.assertIn('id="source-kind"', html)
        self.assertIn('id="end-stage"', html)
        self.assertIn('id="source-content"', html)
        self.assertIn('id="creative-world-scene"', html)
        self.assertIn('id="prompt-positive"', html)
        self.assertIn("/api/start", html)
        self.assertIn("/api/stop", html)
        self.assertIn('id="history-list"', html)
        self.assertIn('id="history-filter-active"', html)
        self.assertIn('id="history-filter-favorites"', html)
        self.assertIn('id="history-load-more"', html)
        self.assertIn('id="detail-actions"', html)
        self.assertIn('id="status-alert"', html)
        self.assertIn(".preview-path", html)
        self.assertIn("detail.generatedImagePath || \"-\"", html)
        self.assertIn("function shouldRenderDetail", html)
        self.assertIn("function toggleFavorite", html)
        self.assertIn("function fetchJson", html)
        self.assertIn("function ensurePublishTargetsLoaded", html)
        self.assertIn("function ensurePublishSocialPostLoaded", html)
        self.assertIn("function savePublishSocialPost", html)
        self.assertIn("function renderPublishSocialPostEditor", html)
        self.assertIn("function renderPublishPanel", html)
        self.assertIn("function bindPublishPanel", html)
        self.assertIn("function waitForPublishJob", html)
        self.assertIn("function normalizeErrorSignal", html)
        self.assertIn("detailSuspendUntil", html)
        self.assertIn("historyFilter", html)
        self.assertIn("historyLimit", html)
        self.assertIn("publishTargetsPayload", html)
        self.assertIn("publishSelectionByRunId", html)
        self.assertIn("/api/publish/targets", html)
        self.assertIn("/api/publish/social-post", html)
        self.assertIn("/api/publish/run", html)
        self.assertIn("/api/publish/jobs/", html)
        self.assertIn("publish-panel", html)
        self.assertIn("publish-social-post-text", html)
        self.assertIn("data-publish-save-social-post", html)
        self.assertIn("data-publish-reset-social-post", html)
        self.assertIn("function saveRunToLocalDirectory", html)
        self.assertIn("function recordClientPublishResult", html)
        self.assertIn("function renderLocalExportEditor", html)
        self.assertIn("function resolveLocalExportOptions", html)
        self.assertIn("function ensureLocalExportDirectoryHandle", html)
        self.assertIn("function readStoredLocalExportDirectoryHandle", html)
        self.assertIn("function writeStoredLocalExportDirectoryHandle", html)
        self.assertIn("function clearStoredLocalExportDirectoryHandle", html)
        self.assertIn("function rerenderCurrentDetail", html)
        self.assertIn("showDirectoryPicker", html)
        self.assertIn("/api/publish/client-result", html)
        self.assertIn('id="publish-local-export-kind"', html)
        self.assertIn('id="publish-local-export-name"', html)
        self.assertIn("data-local-export-change-dir", html)
        self.assertIn("data-local-export-clear-dir", html)
        self.assertIn("content-workbench-local-export-preference-v1", html)
        self.assertIn("content-workbench-local-export-directory-v1", html)
        self.assertIn('type="radio"', html)
        self.assertNotIn('type="checkbox" data-publish-target', html)
        self.assertIn("review-path-input", html)
        self.assertIn("review-path-btn", html)
        self.assertIn("function clearReviewedPathDetail", html)
        self.assertIn("function reviewPathDetail", html)
        self.assertIn("function renderCompareBlocks", html)
        self.assertIn("function requestHasUsableMode", html)
        self.assertIn("function readModePreference", html)
        self.assertIn("function writeModePreference", html)
        self.assertIn("function persistCurrentModePreference", html)
        self.assertIn("const hiddenRefreshMs = Math.max(refreshMs * 4, 30000);", html)
        self.assertIn("function scheduleSnapshotPoll", html)
        self.assertIn("let snapshotFetchPromise = null;", html)
        self.assertIn("let lastHistoryListRenderKey = \"\";", html)
        self.assertIn("let lastDetailRenderKey = \"\";", html)
        self.assertIn("status-alert-title", html)
        self.assertIn("history-error-title", html)
        self.assertIn("function historyListRenderKey", html)
        self.assertIn("function detailRenderKey", html)
        self.assertIn('document.addEventListener("visibilitychange"', html)
        self.assertIn("applyRequestModeToForm(readModePreference(snapshot) || {}, snapshot)", html)
        self.assertIn('sourceSelect.value = "";', html)
        self.assertIn('public-workbench-mode-preference-v1', html)
        self.assertIn('content-workbench-mode-preference-v1', html)
        self.assertIn("function applyRequestModeToForm", html)
        self.assertIn("applyRequestModeToForm(snapshot?.lastRequest || {}, snapshot)", html)
        self.assertNotIn("applyRequestToForm(snapshot.lastRequest || {})", html)
        self.assertIn(".diff-token.changed.after", html)
        self.assertIn("查看原始文件内容", html)
        self.assertIn("ArrowDown", html)
        self.assertNotIn("setInterval(() => {", html)
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
