from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from io_utils import read_json, write_json
from publish.service import (
    list_publish_targets,
    read_publish_job_status,
    record_client_publish_result,
    submit_publish_run,
)
from publish.targets import resolve_publish_targets_for_request
from runtime_layout import runs_root


def _write_targets_config(project_dir: Path, *, include_browser_target: bool = False) -> None:
    config_dir = project_dir / "config" / "publish"
    config_dir.mkdir(parents=True, exist_ok=True)
    targets = {
        "local_archive": {
            "adapter": "local_archive",
            "displayName": "Local Archive",
            "archiveRoot": "runtime/service_state/publish/local_archive",
        },
        "qq_bot_user": {
            "adapter": "qq_bot_user",
            "displayName": "QQ Bot User",
            "scene": "user",
            "configPath": "config/publish/qq_bot_message.json",
            "userOpenIdEnvName": "QQ_BOT_USER_OPENID",
        },
    }
    if include_browser_target:
        targets["pixiv_browser_draft"] = {
            "adapter": "pixiv_browser_draft",
            "displayName": "Pixiv",
            "postUrl": "https://www.pixiv.net/illustration/create",
            "autoSubmit": False,
        }
    write_json(
        config_dir / "targets.json",
        {
            "defaultTargetIds": ["local_archive"],
            "targets": targets,
        },
    )


def _write_run_artifacts(project_dir: Path, run_id: str) -> Path:
    run_dir = runs_root(project_dir) / run_id
    (run_dir / "input").mkdir(parents=True, exist_ok=True)
    (run_dir / "creative").mkdir(parents=True, exist_ok=True)
    (run_dir / "social_post").mkdir(parents=True, exist_ok=True)
    (run_dir / "execution").mkdir(parents=True, exist_ok=True)
    (run_dir / "output").mkdir(parents=True, exist_ok=True)
    image_path = run_dir / "output" / "demo.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    write_json(
        run_dir / "input" / "character_assets_snapshot.json",
        {
            "subjectProfile": {
                "subject_id": "shan_xiaoyi",
                "display_name_zh": "单小伊",
            }
        },
    )
    write_json(
        run_dir / "creative" / "05_creative_package.json",
        {
            "worldDesign": {
                "scenePremiseZh": "深夜便利店",
                "worldSceneZh": "她站在冰柜前看雨。",
            }
        },
    )
    write_json(
        run_dir / "social_post" / "01_social_post_package.json",
        {
            "socialPostText": "她站在便利店门口看雨，像把今天先收好。",
        },
    )
    write_json(
        run_dir / "execution" / "04_execution_package.json",
        {
            "meta": {"createdAt": "2026-04-24T18:30:00"},
            "imagePath": str(image_path),
        },
    )
    write_json(
        run_dir / "output" / "run_summary.json",
        {
            "runId": run_id,
            "sceneDraftPremiseZh": "深夜便利店",
            "generatedImagePath": str(image_path),
            "socialPostText": "她站在便利店门口看雨，像把今天先收好。",
        },
    )
    return run_dir


def _write_edge_local_config(project_dir: Path) -> None:
    fake_edge = project_dir / "tools" / "msedge.exe"
    fake_edge.parent.mkdir(parents=True, exist_ok=True)
    fake_edge.write_text("", encoding="utf-8")
    source_user_data_dir = project_dir / "edge-source"
    profile_dir = source_user_data_dir / "Default"
    (profile_dir / "Network").mkdir(parents=True, exist_ok=True)
    (source_user_data_dir / "Local State").write_text("{}", encoding="utf-8")
    (profile_dir / "Preferences").write_text("{}", encoding="utf-8")
    (profile_dir / "Network" / "Cookies").write_text("cookies", encoding="utf-8")
    write_json(
        project_dir / ".local" / project_dir.name / "publish" / "targets.local.json",
        {
            "edgePublish": {
                "executablePath": str(fake_edge),
                "sourceUserDataDir": str(source_user_data_dir),
                "sourceProfileDir": "Default",
                "managedUserDataDir": str(project_dir / "managed-edge"),
                "managedProfileDir": "Default",
            }
        },
    )


class PublishServiceTests(unittest.TestCase):
    def test_list_publish_targets_exposes_trigger_executors(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            _write_targets_config(project_dir)

            payload = list_publish_targets(project_dir)

        targets = {item["id"]: item for item in payload["targets"]}
        target_ids = list(targets)
        self.assertIn("local_archive", target_ids)
        self.assertIn("qq_bot_user", target_ids)
        self.assertIn("local_directory", target_ids)
        self.assertIn("local_save_as", target_ids)
        self.assertEqual(targets["qq_bot_user"]["executor"], "server")
        self.assertEqual(targets["local_save_as"]["executor"], "browser_save")
        self.assertTrue(targets["local_directory"]["internal"])
        self.assertTrue(targets["local_directory"]["supportsLocalExport"])
        self.assertTrue(targets["local_save_as"]["supportsLocalExport"])
        self.assertEqual(targets["local_save_as"]["defaultLocalExportKind"], "bundle_folder")
        self.assertEqual(
            [item["id"] for item in targets["local_save_as"]["localExportKinds"]],
            ["image_only", "bundle_folder"],
        )
        self.assertEqual(payload["defaultTargetIds"], ["local_archive"])
        self.assertIn("browserProfiles", payload)
        self.assertIn("edge", payload["browserProfiles"])

    def test_submit_publish_run_supports_local_directory_and_updates_run_summary(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            _write_targets_config(project_dir)
            run_id = "2026-04-24T18-30-00_publish_service"
            run_dir = _write_run_artifacts(project_dir, run_id)

            job = submit_publish_run(
                project_dir,
                {
                    "runId": run_id,
                    "localDirectory": "exports/publish-demo",
                    "options": {
                        "localExport": {
                            "kind": "bundle_folder",
                            "name": "Rainy Night:01",
                        }
                    },
                },
            )

            summary_payload = read_json(run_dir / "output" / "run_summary.json")
            job_payload = read_publish_job_status(project_dir, job["jobId"])
            receipts = summary_payload["publishReceipts"]
            image_export_path = Path(receipts[0]["imagePath"])
            text_export_path = Path(receipts[0]["textPath"])
            bundle_path = Path(receipts[0]["bundlePath"])
            exported_text = text_export_path.read_text(encoding="utf-8")

            self.assertEqual(job["status"], "completed")
            self.assertEqual(job_payload["status"], "completed")
            self.assertEqual(receipts[0]["adapter"], "local_directory")
            self.assertEqual(receipts[0]["exportKind"], "bundle_folder")
            self.assertEqual(receipts[0]["exportName"], "Rainy Night_01")
            self.assertEqual(receipts[0]["containerName"], "Rainy Night_01")
            self.assertEqual(summary_payload["lastPublishJobId"], job["jobId"])
            self.assertTrue(bundle_path.exists())
            self.assertTrue(image_export_path.exists())
            self.assertTrue(text_export_path.exists())
            self.assertIn("她站在便利店门口看雨", exported_text)

    def test_record_client_publish_result_updates_run_summary(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            _write_targets_config(project_dir)
            run_id = "2026-04-24T18-35-00_client_publish"
            run_dir = _write_run_artifacts(project_dir, run_id)

            job = record_client_publish_result(
                project_dir,
                {
                    "runId": run_id,
                    "targetId": "local_save_as",
                    "fileNames": ["demo.png", "demo_social_post.txt"],
                    "localExport": {
                        "kind": "bundle_folder",
                        "name": "Rainy Browser Save",
                    },
                    "containerName": "Rainy Browser Save",
                    "directoryLabel": "Downloads",
                },
            )

            summary_payload = read_json(run_dir / "output" / "run_summary.json")
            job_payload = read_publish_job_status(project_dir, job["jobId"])
            receipt = summary_payload["publishReceipts"][0]

            self.assertEqual(job["status"], "completed")
            self.assertEqual(job_payload["status"], "completed")
            self.assertEqual(receipt["targetId"], "local_save_as")
            self.assertEqual(receipt["adapter"], "browser_save")
            self.assertEqual(receipt["status"], "saved")
            self.assertEqual(receipt["fileCount"], 2)
            self.assertEqual(receipt["exportKind"], "bundle_folder")
            self.assertEqual(receipt["exportName"], "Rainy Browser Save")
            self.assertEqual(receipt["containerName"], "Rainy Browser Save")
            self.assertEqual(receipt["directoryLabel"], "Downloads")
            self.assertEqual(summary_payload["lastPublishJobId"], job["jobId"])

    def test_submit_publish_run_supports_image_only_local_directory_export(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            _write_targets_config(project_dir)
            run_id = "2026-04-24T18-31-00_publish_image_only"
            run_dir = _write_run_artifacts(project_dir, run_id)

            job = submit_publish_run(
                project_dir,
                {
                    "runId": run_id,
                    "localDirectory": "exports/publish-image-only",
                    "options": {
                        "localExport": {
                            "kind": "image_only",
                            "name": "Rainy Poster",
                        }
                    },
                },
            )

            summary_payload = read_json(run_dir / "output" / "run_summary.json")
            receipt = summary_payload["publishReceipts"][0]
            image_export_path = Path(receipt["imagePath"])

            self.assertEqual(job["status"], "completed")
            self.assertEqual(receipt["adapter"], "local_directory")
            self.assertEqual(receipt["exportKind"], "image_only")
            self.assertEqual(receipt["exportName"], "Rainy Poster")
            self.assertEqual(receipt["containerName"], "")
            self.assertEqual(receipt["bundlePath"], "")
            self.assertEqual(receipt["textPath"], "")
            self.assertTrue(image_export_path.exists())
            self.assertEqual(image_export_path.name, "Rainy Poster.png")

    def test_browser_target_reports_setup_guidance_until_edge_sync(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            _write_targets_config(project_dir, include_browser_target=True)
            _write_edge_local_config(project_dir)

            payload = list_publish_targets(project_dir)
            pixiv = next(item for item in payload["targets"] if item["id"] == "pixiv_browser_draft")

            self.assertFalse(pixiv["available"])
            self.assertTrue(pixiv["requiresBrowserProfile"])
            self.assertEqual(pixiv["browserProfile"], "edge")
            self.assertIn("sync-edge", pixiv["setupCommand"])
            with self.assertRaisesRegex(RuntimeError, "Edge 发布配置"):
                resolve_publish_targets_for_request(
                    project_dir,
                    target_ids=["pixiv_browser_draft"],
                )


if __name__ == "__main__":
    unittest.main()
