from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from studio.content_workbench_worker import _load_worker_request_payload, run_content_workbench_worker


class ContentWorkbenchWorkerTests(unittest.TestCase):
    def test_load_worker_request_payload_retries_until_request_id_matches(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            with patch(
                "workbench.worker.read_active_request",
                side_effect=[
                    None,
                    {"requestId": "other", "sourceKind": "scene_draft_text"},
                    {
                        "requestId": "req-1",
                        "sourceKind": "scene_draft_text",
                        "endStage": "scene_draft",
                        "label": "demo",
                        "sceneDraftText": "夜里便利店",
                    },
                ],
            ):
                payload = _load_worker_request_payload(project_dir, request_id="req-1", timeout_seconds=0.2)

        self.assertEqual(payload["requestId"], "req-1")

    def test_run_content_workbench_worker_accepts_request_id_bootstrap(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            request_payload = {
                "requestId": "req-1",
                "sourceKind": "scene_draft_text",
                "endStage": "scene_draft",
                "label": "demo",
                "sceneDraftText": "夜里便利店",
            }
            with patch(
                "workbench.worker.read_active_request",
                side_effect=[None, request_payload],
            ), patch(
                "workbench.worker.execute_workbench_task",
                return_value={"summary": {"sceneDraftPremiseZh": "夜里便利店"}, "bundle": None},
            ):
                exit_code = run_content_workbench_worker(project_dir, request_id="req-1")

        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
