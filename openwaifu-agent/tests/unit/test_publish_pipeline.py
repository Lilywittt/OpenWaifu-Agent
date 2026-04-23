from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from io_utils import read_json
from publish.pipeline import run_publish_pipeline
from runtime_layout import create_run_bundle


def _subject_profile() -> dict:
    return {
        "subject_id": "tsukimi_rion",
        "display_name_zh": "demo",
        "identity_zh": ["junior high school girl"],
        "appearance_zh": ["short black hair", "slim build"],
        "psychology_zh": ["sensitive", "curious"],
        "allowed_changes_zh": ["hair accessories may change"],
        "forbidden_drift_zh": ["do not mature the face or body ratio"],
        "notes_zh": [],
    }


class PublishPipelineTests(unittest.TestCase):
    def test_publish_pipeline_builds_publish_input_and_writes_receipts(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            publish_config_dir = project_dir / "config" / "publish"
            publish_config_dir.mkdir(parents=True)
            (publish_config_dir / "targets.json").write_text(
                """
{
  "defaultTargetIds": ["local_archive"],
  "targets": {
    "local_archive": {
      "adapter": "local_archive",
      "displayName": "Local Archive",
      "archiveRoot": "runtime/service_state/publish/local_archive"
    }
  }
}
                """.strip(),
                encoding="utf-8",
            )

            bundle = create_run_bundle(project_dir, "default", "publish-pipeline")
            image_path = bundle.output_dir / "demo.png"
            image_path.write_bytes(b"fake-image")

            character_assets = {"subjectProfile": _subject_profile()}
            creative_package = {
                "worldDesign": {
                    "scenePremiseZh": "demo premise",
                    "worldSceneZh": "demo scene",
                }
            }
            social_post_package = {
                "socialPostText": "demo social post",
            }
            execution_package = {
                "meta": {
                    "createdAt": "2026-04-07T18:00:00",
                },
                "imagePath": str(image_path),
                "checkpointName": "animagine-xl-4.0-opt.safetensors",
            }

            publish_package = run_publish_pipeline(
                project_dir,
                bundle,
                {"runMode": "default", "nowLocal": "2026-04-07T18:00:00"},
                character_assets,
                creative_package,
                social_post_package,
                execution_package,
            )

            publish_input = read_json(bundle.publish_dir / "00_publish_input.json")
            publish_plan = read_json(bundle.publish_dir / "01_publish_plan.json")
            publish_snapshot = read_json(bundle.publish_dir / "04_publish_package.json")
            publish_summary = read_json(bundle.output_dir / "publish_summary.json")
            ledger = read_json(project_dir / "runtime" / "service_state" / "publish" / "published_ledger.json")

            self.assertEqual(publish_input["runId"], bundle.run_id)
            self.assertEqual(publish_input["subjectId"], "tsukimi_rion")
            self.assertEqual(publish_input["scenePremiseZh"], "demo premise")
            self.assertEqual(publish_input["socialPostText"], "demo social post")
            self.assertEqual(publish_input["imageMime"], "image/png")
            self.assertEqual(publish_plan["targets"][0]["targetId"], "local_archive")
            self.assertEqual(publish_snapshot["receipts"][0]["adapter"], "local_archive")
            self.assertEqual(publish_summary["targetCount"], 1)
            self.assertEqual(ledger["records"][0]["runId"], bundle.run_id)
            self.assertEqual(publish_package["receipts"][0]["status"], "published")

    def test_publish_pipeline_accepts_explicit_targets(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            bundle = create_run_bundle(project_dir, "default", "publish-explicit-targets")
            image_path = bundle.output_dir / "demo.png"
            image_path.write_bytes(b"fake-image")

            character_assets = {"subjectProfile": _subject_profile()}
            creative_package = {
                "worldDesign": {
                    "scenePremiseZh": "demo premise",
                    "worldSceneZh": "demo scene",
                }
            }
            social_post_package = {"socialPostText": "demo social post"}
            execution_package = {
                "meta": {"createdAt": "2026-04-08T18:20:00"},
                "imagePath": str(image_path),
            }

            publish_package = run_publish_pipeline(
                project_dir,
                bundle,
                {"runMode": "default", "nowLocal": "2026-04-08T18:20:00"},
                character_assets,
                creative_package,
                social_post_package,
                execution_package,
                explicit_targets=[
                    {
                        "targetId": "local_archive_dynamic",
                        "adapter": "local_archive",
                        "displayName": "Local Archive Dynamic",
                        "archiveRoot": "runtime/service_state/publish/local_archive_dynamic",
                    }
                ],
            )

            publish_plan = read_json(bundle.publish_dir / "01_publish_plan.json")
            self.assertEqual(publish_plan["targets"][0]["targetId"], "local_archive_dynamic")
            self.assertEqual(publish_package["receipts"][0]["targetId"], "local_archive_dynamic")


if __name__ == "__main__":
    unittest.main()
