from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sidecar_control import sidecar_logs_root, sidecar_server_process_path, sidecar_state_root


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


if __name__ == "__main__":
    unittest.main()
