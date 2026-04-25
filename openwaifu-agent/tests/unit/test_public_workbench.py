from __future__ import annotations

import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener, urlopen
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from io_utils import write_json
from runtime_layout import runs_root
from test_pipeline import validate_workbench_request
from workbench.identity import WorkbenchViewer
from workbench.profile import PUBLIC_PROFILE
from workbench.service import WorkbenchManager, _make_handler
from workbench.store import (
    append_run_index_record,
    build_content_workbench_snapshot,
    write_active_worker,
    write_workbench_status,
)


class _FakePublicManager:
    def is_busy(self) -> bool:
        return False

    def start_task(self, payload: dict, *, viewer: WorkbenchViewer) -> dict:
        return {
            **payload,
            "requestId": "req-demo",
            "ownerId": viewer.owner_id,
            "ownerDisplay": viewer.display_name,
        }

    def stop_task(self, *, viewer: WorkbenchViewer) -> dict:
        return {"accepted": True, "alreadyStopping": False}

    def rerun_last(self, *, viewer: WorkbenchViewer) -> dict:
        return {"requestId": "req-rerun", "ownerId": viewer.owner_id}

    def shutdown(self) -> None:
        return


class PublicWorkbenchTests(unittest.TestCase):
    def test_validate_workbench_request_preserves_public_owner_fields(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            normalized = validate_workbench_request(
                project_dir,
                {
                    "sourceKind": "prompt_package_text",
                    "endStage": "image",
                    "label": "public_case",
                    "positivePromptText": "1girl",
                    "negativePromptText": "bad hands",
                    "ownerId": "access:demo",
                    "ownerDisplay": "demo@example.com",
                },
            )

        self.assertEqual(normalized["ownerId"], "access:demo")
        self.assertEqual(normalized["ownerDisplay"], "demo@example.com")

    def test_public_profile_rejects_file_based_source_kind(self):
        with TemporaryDirectory() as temp_dir:
            manager = WorkbenchManager(
                Path(temp_dir),
                profile=PUBLIC_PROFILE,
                worker_command_builder=lambda _request_id: [],
            )
            with self.assertRaisesRegex(RuntimeError, "公共体验模式不支持"):
                manager._assert_public_source_allowed(
                    {
                        "sourceKind": "scene_draft_file",
                        "sourcePath": "runtime/runs/demo/creative/01_world_design.json",
                        "endStage": "image",
                    }
                )

    def test_public_snapshot_only_returns_current_owner_history(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_a = runs_root(project_dir) / "2026-04-21T20-00-00_public_a"
            run_b = runs_root(project_dir) / "2026-04-21T20-10-00_public_b"
            for run_dir in (run_a, run_b):
                (run_dir / "output").mkdir(parents=True, exist_ok=True)
                write_json(run_dir / "output" / "run_summary.json", {"runId": run_dir.name})
            append_run_index_record(
                project_dir,
                {
                    "status": "completed",
                    "runId": run_a.name,
                    "runRoot": str(run_a),
                    "summaryPath": str(run_a / "output" / "run_summary.json"),
                    "request": {
                        "label": "mine",
                        "sourceKind": "scene_draft_text",
                        "endStage": "image",
                        "ownerId": "access:me",
                        "ownerDisplay": "me@example.com",
                    },
                },
            )
            append_run_index_record(
                project_dir,
                {
                    "status": "completed",
                    "runId": run_b.name,
                    "runRoot": str(run_b),
                    "summaryPath": str(run_b / "output" / "run_summary.json"),
                    "request": {
                        "label": "other",
                        "sourceKind": "scene_draft_text",
                        "endStage": "image",
                        "ownerId": "access:other",
                        "ownerDisplay": "other@example.com",
                    },
                },
            )

            snapshot = build_content_workbench_snapshot(
                project_dir,
                viewer=WorkbenchViewer(
                    owner_id="access:me",
                    display_name="me@example.com",
                    email="me@example.com",
                    authenticated=True,
                    public=True,
                ),
                profile=PUBLIC_PROFILE,
            )

        self.assertEqual([item["runId"] for item in snapshot["history"]], [run_a.name])
        self.assertEqual([item["id"] for item in snapshot["config"]["historyFilters"]], ["active", "all"])
        self.assertFalse(snapshot["config"]["permissions"]["allowFavorites"])
        self.assertFalse(snapshot["config"]["permissions"]["allowDeleteRun"])

    def test_public_snapshot_masks_running_task_from_other_owner(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            write_workbench_status(
                project_dir,
                {
                    "status": "running",
                    "stage": "准备测试输入",
                    "runId": "run-foreign",
                    "runRoot": str(runs_root(project_dir) / "run-foreign"),
                    "request": {
                        "sourceKind": "scene_draft_text",
                        "endStage": "image",
                        "label": "foreign",
                        "ownerId": "access:other",
                    },
                },
            )
            write_active_worker(project_dir, {"pid": 12345, "startedAt": "2026-04-21T20:00:00"})
            with patch("workbench.store.is_process_alive", return_value=True):
                snapshot = build_content_workbench_snapshot(
                    project_dir,
                    viewer=WorkbenchViewer(
                        owner_id="access:me",
                        display_name="me@example.com",
                        email="me@example.com",
                        authenticated=True,
                        public=True,
                    ),
                    profile=PUBLIC_PROFILE,
                )

        self.assertEqual(snapshot["status"]["status"], "running")
        self.assertEqual(snapshot["status"]["runId"], "")
        self.assertEqual(snapshot["status"]["request"], {})
        self.assertTrue(snapshot["status"]["busy"])
        self.assertFalse(snapshot["status"]["canStop"])

    def test_public_snapshot_keeps_current_owner_running_task_visible(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_dir = runs_root(project_dir) / "2026-04-21T20-30-00_public_me"
            (run_dir / "output").mkdir(parents=True, exist_ok=True)
            write_json(run_dir / "output" / "run_summary.json", {"runId": run_dir.name})
            write_workbench_status(
                project_dir,
                {
                    "status": "running",
                    "stage": "execution layer",
                    "runId": run_dir.name,
                    "runRoot": str(run_dir),
                    "request": {
                        "sourceKind": "prompt_package_text",
                        "endStage": "image",
                        "label": "mine",
                        "ownerId": "access:me",
                        "ownerDisplay": "me@example.com",
                    },
                },
            )
            write_active_worker(project_dir, {"pid": 12345, "startedAt": "2026-04-21T20:30:00"})
            with patch("workbench.store.is_process_alive", return_value=True):
                snapshot = build_content_workbench_snapshot(
                    project_dir,
                    viewer=WorkbenchViewer(
                        owner_id="access:me",
                        display_name="me@example.com",
                        email="me@example.com",
                        authenticated=True,
                        public=True,
                    ),
                    profile=PUBLIC_PROFILE,
                )

        self.assertEqual(snapshot["status"]["status"], "running")
        self.assertEqual(snapshot["status"]["runId"], run_dir.name)
        self.assertFalse(snapshot["status"]["canStop"])
        self.assertIsNotNone(snapshot["currentRunItem"])
        self.assertEqual(snapshot["currentRunItem"]["runId"], run_dir.name)
        self.assertEqual(snapshot["selectedRunId"], run_dir.name)
        self.assertIsNotNone(snapshot["selectedRunDetail"])
        self.assertEqual(snapshot["selectedRunDetail"]["runId"], run_dir.name)

    def test_public_manager_rejects_stop_task(self):
        with TemporaryDirectory() as temp_dir:
            manager = WorkbenchManager(
                Path(temp_dir),
                profile=PUBLIC_PROFILE,
                worker_command_builder=lambda _request_id: [],
            )
            with self.assertRaisesRegex(RuntimeError, "不提供停止任务"):
                manager.stop_task(
                    viewer=WorkbenchViewer(
                        owner_id="access:me",
                        display_name="me@example.com",
                        email="me@example.com",
                        authenticated=True,
                        public=True,
                    )
                )

    def test_public_handler_rejects_private_only_actions(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            handler = _make_handler(
                project_dir=project_dir,
                refresh_seconds=5,
                history_limit=10,
                manager=_FakePublicManager(),
                profile=PUBLIC_PROFILE,
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            server.daemon_threads = True
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                headers = {
                    "Content-Type": "application/json",
                    "CF-Access-Authenticated-User-Email": "friend@example.com",
                    "CF-Access-Authenticated-User-Name": "friend",
                }
                with urlopen(base_url + "/api/healthz", timeout=2) as response:
                    health = json.loads(response.read().decode("utf-8"))

                blocked_paths = [
                    ("GET", "/api/publish/targets", None),
                    ("GET", "/api/publish/jobs/demo-job", None),
                    ("POST", "/api/publish/run", {"runId": "run-1", "targets": ["qq_bot_user"]}),
                    ("POST", "/api/publish/client-result", {"runId": "run-1", "targetId": "local_save_as"}),
                    ("POST", "/api/review-path", {"path": str(project_dir)}),
                    ("POST", "/api/toggle-favorite", {"kind": "run", "runId": "run-1"}),
                    ("POST", "/api/delete-run", {"runId": "run-1"}),
                    ("POST", "/api/shutdown", {}),
                ]
                statuses: list[int] = []
                for method, path, payload in blocked_paths:
                    opener = build_opener(ProxyHandler({}))
                    request = Request(
                        base_url + path,
                        data=(json.dumps(payload).encode("utf-8") if payload is not None else None),
                        headers={**headers, "Connection": "close"},
                        method=method,
                    )
                    try:
                        with opener.open(request, timeout=2):
                            pass
                    except HTTPError as exc:
                        statuses.append(exc.code)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertEqual(health["service"], "public_workbench")
        self.assertEqual(statuses, [403, 403, 403, 403, 403, 403, 403, 403])


if __name__ == "__main__":
    unittest.main()
