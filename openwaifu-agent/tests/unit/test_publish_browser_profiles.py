from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from io_utils import read_json, write_json
from publish.browser_profiles import (
    cleanup_edge_publish_sessions,
    edge_publish_sessions_root,
    load_edge_publish_profile,
    read_edge_publish_profile_status,
    sync_edge_publish_profile,
)


def _write_local_config(project_dir: Path, payload: dict) -> Path:
    config_path = project_dir / ".local" / project_dir.name / "publish" / "targets.local.json"
    write_json(config_path, payload)
    return config_path


def _write_source_profile(source_user_data_dir: Path) -> None:
    profile_dir = source_user_data_dir / "Default"
    (profile_dir / "Network").mkdir(parents=True, exist_ok=True)
    (profile_dir / "Local Storage").mkdir(parents=True, exist_ok=True)
    (profile_dir / "Session Storage").mkdir(parents=True, exist_ok=True)
    (profile_dir / "IndexedDB").mkdir(parents=True, exist_ok=True)
    (profile_dir / "Storage").mkdir(parents=True, exist_ok=True)
    (profile_dir / "Service Worker").mkdir(parents=True, exist_ok=True)
    (source_user_data_dir / "Local State").write_text("{}", encoding="utf-8")
    (profile_dir / "Preferences").write_text("{}", encoding="utf-8")
    (profile_dir / "Secure Preferences").write_text("{}", encoding="utf-8")
    (profile_dir / "Login Data").write_text("login", encoding="utf-8")
    (profile_dir / "Web Data").write_text("web", encoding="utf-8")
    (profile_dir / "Network" / "Cookies").write_text("cookies", encoding="utf-8")


class PublishBrowserProfileTests(unittest.TestCase):
    def test_load_edge_publish_profile_uses_local_config(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            fake_edge = project_dir / "tools" / "msedge.exe"
            fake_edge.parent.mkdir(parents=True, exist_ok=True)
            fake_edge.write_text("", encoding="utf-8")
            source_user_data_dir = project_dir / "edge-source"
            managed_user_data_dir = project_dir / "managed-edge"
            _write_local_config(
                project_dir,
                {
                    "edgePublish": {
                        "executablePath": str(fake_edge),
                        "sourceUserDataDir": str(source_user_data_dir),
                        "sourceProfileDir": "Default",
                        "managedUserDataDir": str(managed_user_data_dir),
                        "managedProfileDir": "Default",
                    }
                },
            )

            profile = load_edge_publish_profile(project_dir)

        self.assertEqual(profile.executable_path, fake_edge.resolve())
        self.assertEqual(profile.source_user_data_dir, source_user_data_dir.resolve())
        self.assertEqual(profile.managed_user_data_dir, managed_user_data_dir.resolve())

    def test_sync_edge_publish_profile_copies_required_files_and_writes_manifest(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            fake_edge = project_dir / "tools" / "msedge.exe"
            fake_edge.parent.mkdir(parents=True, exist_ok=True)
            fake_edge.write_text("", encoding="utf-8")
            source_user_data_dir = project_dir / "edge-source"
            managed_user_data_dir = project_dir / "managed-edge"
            _write_source_profile(source_user_data_dir)
            local_config_path = _write_local_config(
                project_dir,
                {
                    "edgePublish": {
                        "executablePath": str(fake_edge),
                        "sourceUserDataDir": str(source_user_data_dir),
                        "sourceProfileDir": "Default",
                        "managedUserDataDir": str(managed_user_data_dir),
                        "managedProfileDir": "Default",
                    }
                },
            )

            before_status = read_edge_publish_profile_status(project_dir)
            sync_payload = sync_edge_publish_profile(project_dir)
            after_status = read_edge_publish_profile_status(project_dir)
            managed_root = Path(sync_payload["managedUserDataDir"])
            manifest_payload = read_json(managed_root / "edge_publish_manifest.json")

            self.assertFalse(before_status["managedReady"])
            self.assertFalse(before_status["readyForPublish"])
            self.assertEqual(before_status["statusCode"], "sync_required")
            self.assertTrue(after_status["managedReady"])
            self.assertTrue(after_status["readyForPublish"])
            self.assertEqual(after_status["statusCode"], "ready")
            self.assertIn("sync-edge", after_status["guidance"])
            self.assertIn("cleanup-sessions", after_status["cleanupCommand"])
            self.assertEqual(sync_payload["localConfigPath"], str(local_config_path))
            self.assertEqual(manifest_payload["sourceProfileDir"], "Default")
            self.assertTrue((managed_root / "Local State").exists())
            self.assertTrue((managed_root / "Default" / "Preferences").exists())
            self.assertTrue((managed_root / "Default" / "Network" / "Cookies").exists())

    def test_cleanup_edge_publish_sessions_removes_session_dirs(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            sessions_root = edge_publish_sessions_root(project_dir)
            (sessions_root / "session-a").mkdir(parents=True, exist_ok=True)
            (sessions_root / "session-b").mkdir(parents=True, exist_ok=True)

            payload = cleanup_edge_publish_sessions(project_dir)

        self.assertEqual(payload["removedCount"], 2)
        self.assertEqual(payload["skippedCount"], 0)


if __name__ == "__main__":
    unittest.main()
