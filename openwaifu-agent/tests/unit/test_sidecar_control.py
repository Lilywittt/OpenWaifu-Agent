from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sidecar_control import (
    HttpSidecarSpec,
    read_sidecar_server_process,
    record_http_sidecar,
    sidecar_logs_root,
    sidecar_server_process_path,
    sidecar_state_root,
    status_http_sidecar,
)


class SidecarControlTests(unittest.TestCase):
    def test_sidecar_state_root_migrates_legacy_ops_state(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            legacy_root = project_dir / "runtime" / "service_state" / "ops" / "content_workbench"
            legacy_root.mkdir(parents=True, exist_ok=True)
            legacy_payload = {"pid": 12345}
            (legacy_root / "server_process.json").write_text(
                json.dumps(legacy_payload, ensure_ascii=False),
                encoding="utf-8",
            )

            resolved_root = sidecar_state_root(project_dir, "content_workbench")
            process_path = sidecar_server_process_path(project_dir, "content_workbench")

            self.assertEqual(
                resolved_root,
                project_dir / "runtime" / "service_state" / "sidecars" / "content_workbench",
            )
            self.assertTrue(process_path.exists())
            self.assertEqual(
                json.loads(process_path.read_text(encoding="utf-8")),
                legacy_payload,
            )
            self.assertFalse(legacy_root.exists())

    def test_sidecar_logs_root_uses_sidecars_namespace(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            logs_root = sidecar_logs_root(project_dir, "ops_dashboard")

        self.assertEqual(
            logs_root,
            project_dir / "runtime" / "service_logs" / "sidecars" / "ops_dashboard",
        )

    def test_record_http_sidecar_skips_rewrite_when_payload_is_unchanged(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            process_path = sidecar_server_process_path(project_dir, "content_workbench")
            process_path.write_text(
                json.dumps(
                    {
                        "pid": 12196,
                        "browserUrl": "http://127.0.0.1:8766",
                        "port": 8766,
                        "updatedAt": "2026-04-13T13:37:36",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            original_text = process_path.read_text(encoding="utf-8")
            spec = HttpSidecarSpec(
                sidecar_id="content_workbench",
                label="content-workbench",
                project_dir=project_dir,
                browser_url="http://127.0.0.1:8766",
                port=8766,
                stdout_log_path=project_dir / "stdout.log",
                stderr_log_path=project_dir / "stderr.log",
                fetch_health=lambda _url: None,
            )

            with patch("sidecar_control.write_sidecar_server_process") as write_mock:
                record_http_sidecar(spec, 12196)

            self.assertFalse(write_mock.called)
            self.assertEqual(process_path.read_text(encoding="utf-8"), original_text)

    def test_status_http_sidecar_returns_healthy_even_when_record_write_fails(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            spec = HttpSidecarSpec(
                sidecar_id="content_workbench",
                label="content-workbench",
                project_dir=project_dir,
                browser_url="http://127.0.0.1:8766",
                port=8766,
                stdout_log_path=project_dir / "stdout.log",
                stderr_log_path=project_dir / "stderr.log",
                fetch_health=lambda _url: {"serverPid": 12196},
            )

            with patch("sidecar_control.find_tcp_listening_pid", return_value=12196), patch(
                "sidecar_control.is_process_alive",
                return_value=True,
            ), patch(
                "sidecar_control.write_sidecar_server_process",
                side_effect=PermissionError("denied"),
            ):
                status = status_http_sidecar(spec)

            self.assertTrue(status["healthy"])
            self.assertEqual(status["pid"], 12196)
            self.assertTrue(status["pidAlive"])
            self.assertIsNone(read_sidecar_server_process(project_dir, "content_workbench"))


if __name__ == "__main__":
    unittest.main()
