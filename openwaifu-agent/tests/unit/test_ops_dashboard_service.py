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
from ops.dashboard_service import (
    _make_handler,
    dashboard_browser_url,
    probe_existing_dashboard,
    run_dashboard_server,
)
from runtime_layout import runs_root
from http.server import ThreadingHTTPServer


class OpsDashboardServiceTests(unittest.TestCase):
    def test_dashboard_browser_url_maps_wildcard_host_to_loopback(self):
        self.assertEqual(dashboard_browser_url("0.0.0.0", 8765), "http://127.0.0.1:8765")
        self.assertEqual(dashboard_browser_url("::", 8765), "http://127.0.0.1:8765")
        self.assertEqual(dashboard_browser_url("127.0.0.1", 8765), "http://127.0.0.1:8765")

    def test_probe_existing_dashboard_returns_false_for_unreachable_url(self):
        self.assertFalse(probe_existing_dashboard("http://127.0.0.1:65534", timeout_seconds=1))

    def test_run_dashboard_server_reuses_existing_instance_when_port_is_busy(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            with patch("ops.dashboard_service.ThreadingHTTPServer", side_effect=OSError("address already in use")):
                with patch("ops.dashboard_service.probe_existing_dashboard", return_value=True):
                    run_dashboard_server(
                        project_dir,
                        host="127.0.0.1",
                        port=8765,
                        open_browser=False,
                    )

    def test_dashboard_handler_serves_html_and_generated_image(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            (project_dir / ".env").write_text("QQ_BOT_DISPLAY_NAME=单小伊 Agent\n", encoding="utf-8")
            run_dir = runs_root(project_dir) / "2026-04-11T18-30-00_qqbot_generate_demo"
            (run_dir / "output").mkdir(parents=True, exist_ok=True)
            image_path = run_dir / "output" / "demo.png"
            image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            write_json(
                run_dir / "output" / "run_summary.json",
                {
                    "runId": run_dir.name,
                    "generatedImagePath": str(image_path),
                    "sceneDraftPremiseZh": "测试标题",
                },
            )
            write_json(
                run_dir / "prompt_builder" / "01_prompt_package.json",
                {
                    "positivePrompt": "masterpiece, solo, girl",
                    "negativePrompt": "bad hands, nsfw",
                },
            )
            handler = _make_handler(
                project_dir=project_dir,
                dashboard_title="单小伊 Agent 运维面板",
                refresh_seconds=5,
                queue_limit=20,
                recent_job_limit=12,
                event_limit=20,
                run_limit=8,
                log_tail_lines=20,
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            server.daemon_threads = True
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                with urlopen(base_url + "/", timeout=2) as response:
                    html = response.read().decode("utf-8")
                with urlopen(
                    base_url + f"/runs/detail?runId={run_dir.name}",
                    timeout=2,
                ) as response:
                    detail_html = response.read().decode("utf-8")
                with urlopen(
                    base_url + f"/api/run-detail?runId={run_dir.name}",
                    timeout=2,
                ) as response:
                    detail_payload = response.read().decode("utf-8")
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

        self.assertIn("单小伊 Agent 运维面板", html)
        self.assertIn("最终送给生图基座的 Prompt", detail_html)
        self.assertIn("最终生图 Prompt", detail_payload)
        self.assertEqual(content_type, "image/png")
        self.assertEqual(image_bytes, b"\x89PNG\r\n\x1a\n")


    def test_dashboard_handler_can_toggle_shared_favorite(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            (project_dir / ".env").write_text("QQ_BOT_DISPLAY_NAME=单小伊 Agent\n", encoding="utf-8")
            run_dir = runs_root(project_dir) / "2026-04-11T18-30-00_qqbot_generate_demo"
            (run_dir / "output").mkdir(parents=True, exist_ok=True)
            write_json(
                run_dir / "output" / "run_summary.json",
                {
                    "runId": run_dir.name,
                    "sceneDraftPremiseZh": "收藏接口测试",
                },
            )
            handler = _make_handler(
                project_dir=project_dir,
                dashboard_title="单小伊 Agent 运维面板",
                refresh_seconds=5,
                queue_limit=20,
                recent_job_limit=12,
                event_limit=20,
                run_limit=8,
                log_tail_lines=20,
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            server.daemon_threads = True
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                request = Request(
                    base_url + "/api/toggle-favorite",
                    data=json.dumps(
                        {
                            "kind": "run",
                            "runId": run_dir.name,
                            "runRoot": str(run_dir),
                        }
                    ).encode("utf-8"),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(request, timeout=2) as response:
                    payload = response.read().decode("utf-8")
                with urlopen(
                    base_url + f"/api/run-detail?runId={run_dir.name}",
                    timeout=2,
                ) as response:
                    detail_payload = response.read().decode("utf-8")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertIn('"favorited": true', payload)
        self.assertIn('"favorite": true', detail_payload)


if __name__ == "__main__":
    unittest.main()
