from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from io_utils import write_json
from runtime_layout import runs_root
from studio.content_workbench_service import (
    _make_handler,
    ContentWorkbenchManager,
    content_workbench_browser_url,
    probe_existing_content_workbench,
)
from studio.content_workbench_store import (
    content_workbench_state_root,
    is_workbench_stop_requested,
    read_active_worker,
    read_workbench_status,
)


class _FakeManager:
    def __init__(self):
        self.start_calls: list[dict] = []

    def is_busy(self) -> bool:
        return False

    def start_task(self, payload: dict) -> dict:
        self.start_calls.append(payload)
        return {"sourceKind": payload.get("sourceKind", "")}

    def stop_task(self) -> dict:
        return {"accepted": True, "alreadyStopping": False}

    def rerun_last(self) -> dict:
        return {"sourceKind": "scene_draft_text"}


class ContentWorkbenchServiceTests(unittest.TestCase):
    def test_browser_url_maps_wildcard_host_to_loopback(self):
        self.assertEqual(content_workbench_browser_url("0.0.0.0", 8766), "http://127.0.0.1:8766")
        self.assertEqual(content_workbench_browser_url("::", 8766), "http://127.0.0.1:8766")

    def test_probe_existing_returns_false_for_unreachable_instance(self):
        self.assertFalse(probe_existing_content_workbench("http://127.0.0.1:65534", timeout_seconds=1))

    def test_handler_serves_html_snapshot_and_start_endpoint(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            (project_dir / ".env").write_text("QQ_BOT_DISPLAY_NAME=单小伊 Agent\n", encoding="utf-8")
            run_dir = runs_root(project_dir) / "2026-04-11T21-00-00_content_workbench"
            (run_dir / "output").mkdir(parents=True, exist_ok=True)
            image_path = run_dir / "output" / "demo.png"
            image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            write_json(
                run_dir / "output" / "run_summary.json",
                {
                    "runId": run_dir.name,
                    "sceneDraftPremiseZh": "夜便利店",
                    "generatedImagePath": str(image_path),
                },
            )
            manager = _FakeManager()
            handler = _make_handler(
                project_dir=project_dir,
                refresh_seconds=5,
                history_limit=10,
                manager=manager,
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            server.daemon_threads = True
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                with urlopen(base_url + "/", timeout=2) as response:
                    html = response.read().decode("utf-8")
                with urlopen(base_url + "/api/healthz", timeout=2) as response:
                    health_payload = json.loads(response.read().decode("utf-8"))
                with urlopen(base_url + "/api/snapshot", timeout=2) as response:
                    snapshot_payload = json.loads(response.read().decode("utf-8"))
                request = Request(
                    base_url + "/api/start",
                    data=json.dumps({"sourceKind": "scene_draft_text", "endStage": "prompt", "sceneDraftText": "便利店夜雨"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=2) as response:
                    start_payload = json.loads(response.read().decode("utf-8"))
                with urlopen(
                    base_url + f"/artifacts/generated-image?runId={run_dir.name}",
                    timeout=2,
                ) as response:
                    image_bytes = response.read()
                    content_type = response.headers.get_content_type()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertIn("内容测试工作台", html)
        self.assertTrue(health_payload["ok"])
        self.assertEqual(health_payload["service"], "content_workbench")
        self.assertIn("identity", snapshot_payload)
        self.assertTrue(start_payload["ok"])
        self.assertEqual(manager.start_calls[0]["sourceKind"], "scene_draft_text")
        self.assertEqual(content_type, "image/png")
        self.assertEqual(image_bytes, b"\x89PNG\r\n\x1a\n")

    def test_handler_review_path_returns_detail_for_run_directory(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_dir = runs_root(project_dir) / "2026-04-11T21-00-00_content_workbench"
            creative_dir = run_dir / "creative"
            output_dir = run_dir / "output"
            creative_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)
            write_json(
                creative_dir / "01_world_design.json",
                {"scenePremiseZh": "深夜便利店", "worldSceneZh": "她在玻璃窗边写字。"},
            )
            write_json(output_dir / "run_summary.json", {"runId": run_dir.name, "sceneDraftPremiseZh": "深夜便利店"})
            manager = _FakeManager()
            handler = _make_handler(
                project_dir=project_dir,
                refresh_seconds=5,
                history_limit=10,
                manager=manager,
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            server.daemon_threads = True
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                request = Request(
                    base_url + "/api/review-path",
                    data=json.dumps({"path": str(creative_dir)}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=2) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["detail"]["runRoot"], str(run_dir))
        self.assertEqual(payload["detail"]["detailTitle"], "深夜便利店")

    def test_handler_toggle_favorite_and_review_path_reflect_state(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_dir = runs_root(project_dir) / "2026-04-11T21-00-00_favorite_path"
            creative_dir = run_dir / "creative"
            output_dir = run_dir / "output"
            creative_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)
            write_json(
                creative_dir / "01_world_design.json",
                {"scenePremiseZh": "收藏目录", "worldSceneZh": "这里测试目录收藏"},
            )
            write_json(output_dir / "run_summary.json", {"runId": run_dir.name, "sceneDraftPremiseZh": "收藏目录"})
            manager = _FakeManager()
            handler = _make_handler(
                project_dir=project_dir,
                refresh_seconds=5,
                history_limit=10,
                manager=manager,
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            server.daemon_threads = True
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                toggle_request = Request(
                    base_url + "/api/toggle-favorite",
                    data=json.dumps({"kind": "path", "path": str(creative_dir), "label": "creative_dir"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(toggle_request, timeout=2) as response:
                    toggle_payload = json.loads(response.read().decode("utf-8"))
                review_request = Request(
                    base_url + "/api/review-path",
                    data=json.dumps({"path": str(creative_dir)}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(review_request, timeout=2) as response:
                    review_payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertTrue(toggle_payload["ok"])
        self.assertTrue(toggle_payload["favorited"])
        self.assertTrue(review_payload["favorite"])
        self.assertTrue(review_payload["detail"]["favorite"])

    def test_snapshot_reconciles_stale_running_status(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            write_json(
                content_workbench_state_root(project_dir) / "latest_status.json",
                {"status": "running", "stage": "准备测试输入", "runId": "", "runRoot": "", "request": {}},
            )
            manager = _FakeManager()
            handler = _make_handler(
                project_dir=project_dir,
                refresh_seconds=5,
                history_limit=10,
                manager=manager,
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            server.daemon_threads = True
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                with urlopen(base_url + "/api/snapshot", timeout=2) as response:
                    snapshot_payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertEqual(snapshot_payload["status"]["status"], "interrupted")

    def test_manager_rejects_when_generation_slot_is_held_elsewhere(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            manager = ContentWorkbenchManager(project_dir)
            with patch(
                "workbench.service.read_generation_slot",
                return_value={
                    "ownerType": "qq_bot_service",
                    "ownerLabel": "QQ 私聊服务",
                    "runId": "run-001",
                    "busyMessage": "本机当前正被QQ 私聊服务占用，暂时不能开始新的内容任务。",
                },
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    manager.start_task(
                        {
                            "sourceKind": "scene_draft_text",
                            "endStage": "prompt",
                            "label": "slot_busy",
                            "sceneDraftText": "夜里便利店",
                        }
                    )
        self.assertIn("本机当前正被", str(ctx.exception))

    def test_manager_start_task_spawns_detached_worker_state(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            manager = ContentWorkbenchManager(project_dir)

            with patch(
                "workbench.service.read_generation_slot",
                return_value=None,
            ), patch.object(
                ContentWorkbenchManager,
                "_launch_worker_process",
                return_value=24680,
            ), patch(
                "studio.content_workbench_service.ContentWorkbenchManager._wait_for_worker_bootstrap",
                return_value=None,
            ):
                request = manager.start_task(
                    {
                        "sourceKind": "scene_draft_text",
                        "endStage": "prompt",
                        "label": "spawned",
                        "sceneDraftText": "便利店夜景",
                        }
                    )
            worker_payload = read_active_worker(project_dir, cleanup_stale=False)
            status_payload = read_workbench_status(project_dir) or {}

        self.assertEqual(request["label"], "spawned")
        self.assertIsNone(worker_payload)
        self.assertEqual(status_payload["status"], "running")
        self.assertEqual(status_payload["stage"], "准备测试输入")

    def test_manager_start_task_marks_failed_when_worker_never_bootstraps(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            manager = ContentWorkbenchManager(project_dir)
            with patch(
                "workbench.service.read_generation_slot",
                return_value=None,
            ), patch.object(
                ContentWorkbenchManager,
                "_launch_worker_process",
                return_value=24680,
            ), patch.object(
                ContentWorkbenchManager,
                "_wait_for_worker_bootstrap",
                side_effect=RuntimeError("内容测试 worker 未成功启动，请查看 worker 日志。"),
            ):
                with self.assertRaises(RuntimeError):
                    manager.start_task(
                        {
                            "sourceKind": "scene_draft_text",
                            "endStage": "prompt",
                            "label": "bootstrap_failed",
                            "sceneDraftText": "便利店夜景",
                        }
                    )
            status_payload = read_workbench_status(project_dir) or {}

        self.assertEqual(status_payload["status"], "failed")
        self.assertIn("worker", status_payload["error"])

    def test_manager_start_task_resets_status_when_worker_spawn_fails(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            manager = ContentWorkbenchManager(project_dir)
            with patch(
                "workbench.service.read_generation_slot",
                return_value=None,
            ), patch.object(
                ContentWorkbenchManager,
                "_launch_worker_process",
                side_effect=RuntimeError("worker failed"),
            ):
                with self.assertRaises(RuntimeError):
                    manager.start_task(
                        {
                            "sourceKind": "scene_draft_text",
                            "endStage": "prompt",
                            "label": "spawn_failed",
                            "sceneDraftText": "便利店夜景",
                        }
                    )
            status_payload = json.loads(
                (content_workbench_state_root(project_dir) / "latest_status.json").read_text(encoding="utf-8")
            )

        self.assertEqual(status_payload["status"], "failed")
        self.assertEqual(status_payload["error"], "worker failed")

    def test_manager_stop_task_creates_stop_request(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            manager = ContentWorkbenchManager(project_dir)
            write_json(
                content_workbench_state_root(project_dir) / "latest_status.json",
                {"status": "running", "stage": "execution layer", "runId": "run-001"},
            )
            with patch("workbench.service.read_active_worker", return_value={"pid": 24680}):
                result = manager.stop_task()

            self.assertTrue(is_workbench_stop_requested(project_dir))

        self.assertTrue(result["accepted"])
        self.assertFalse(result["alreadyStopping"])
        self.assertFalse(result["forced"])

    def test_manager_second_stop_forces_worker_termination(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            manager = ContentWorkbenchManager(project_dir)
            run_dir = runs_root(project_dir) / "run-001"
            (run_dir / "output").mkdir(parents=True, exist_ok=True)
            write_json(run_dir / "output" / "run_summary.json", {"runId": "run-001"})
            write_json(
                content_workbench_state_root(project_dir) / "latest_status.json",
                {
                    "status": "stopping",
                    "stage": "creative layer",
                    "runId": "run-001",
                    "runRoot": str(run_dir),
                    "request": {
                        "sourceKind": "live_sampling",
                        "endStage": "image",
                        "label": "实时采样全链路",
                    },
                    "startedAt": "2026-04-22T22:05:27",
                },
            )
            with patch("workbench.service.read_active_worker", return_value={"pid": 24680}), patch(
                "workbench.service.terminate_process_tree",
                return_value=True,
            ), patch("workbench.service.is_process_alive", return_value=False):
                result = manager.stop_task()
            status_payload = read_workbench_status(project_dir) or {}

        self.assertTrue(result["accepted"])
        self.assertTrue(result["alreadyStopping"])
        self.assertTrue(result["forced"])
        self.assertEqual(status_payload["status"], "interrupted")
        self.assertEqual(status_payload["error"], "当前内容生成已被强制停止。")


if __name__ == "__main__":
    unittest.main()
