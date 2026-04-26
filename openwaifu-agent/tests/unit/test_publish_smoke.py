from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from io_utils import read_json, write_json
from tools.publishing.smoke_publish import run_publish_smoke, summarize_publish_smoke


def _write_run(project_dir: Path, run_id: str) -> Path:
    run_dir = project_dir / "runtime" / "runs" / run_id
    (run_dir / "input").mkdir(parents=True, exist_ok=True)
    (run_dir / "creative").mkdir(parents=True, exist_ok=True)
    (run_dir / "social_post").mkdir(parents=True, exist_ok=True)
    (run_dir / "execution").mkdir(parents=True, exist_ok=True)
    (run_dir / "output").mkdir(parents=True, exist_ok=True)
    image_path = run_dir / "output" / "demo.png"
    image_path.write_bytes(b"fake-image")
    write_json(run_dir / "input" / "character_assets_snapshot.json", {"subjectProfile": {"subject_id": "demo"}})
    write_json(run_dir / "creative" / "05_creative_package.json", {"worldDesign": {"scenePremiseZh": "demo"}})
    write_json(run_dir / "social_post" / "01_social_post_package.json", {"socialPostText": "demo caption"})
    write_json(run_dir / "execution" / "04_execution_package.json", {"imagePath": str(image_path)})
    return run_dir


class PublishSmokeTests(unittest.TestCase):
    def test_smoke_disables_auto_submit_and_writes_artifacts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_dir = _write_run(project_dir, "smoke-run")

            def fake_adapter(**kwargs):
                self.assertFalse(kwargs["target_config"]["autoSubmit"])
                return {
                    "targetId": kwargs["target_id"],
                    "adapter": "fake_browser",
                    "status": "draft_prepared",
                    "captionFilled": True,
                    "imageUploaded": True,
                }

            with patch(
                "tools.publishing.smoke_publish.resolve_publish_targets_for_request",
                return_value=[
                    {
                        "targetId": "fake_target",
                        "adapter": "fake_browser",
                        "autoSubmit": True,
                    }
                ],
            ), patch("tools.publishing.smoke_publish.get_publish_adapter", return_value=fake_adapter):
                report = run_publish_smoke(project_dir, run_id="smoke-run", target_ids=["fake_target"])

            self.assertEqual(report["meta"]["passedCount"], 1)
            self.assertEqual(report["meta"]["failedCount"], 0)
            artifacts_path = Path(report["meta"]["artifactsPath"])
            self.assertTrue((artifacts_path / "publish_smoke_report.json").exists())
            self.assertTrue((artifacts_path / "01_fake_target_request.json").exists())
            request_payload = read_json(artifacts_path / "01_fake_target_request.json")
            self.assertFalse(request_payload["target"]["autoSubmit"])
            self.assertIn(str(run_dir / "output" / "demo.png"), str(request_payload["publishInput"]["imagePath"]))

    def test_smoke_summary_includes_key_receipt_flags(self) -> None:
        report = {
            "meta": {
                "runId": "demo-run",
                "targetCount": 1,
                "passedCount": 1,
                "failedCount": 0,
                "allowSubmit": False,
                "artifactsPath": "runtime/runs/demo/publish/smoke_jobs/1",
            },
            "results": [
                {
                    "targetId": "bilibili_dynamic",
                    "passed": True,
                    "receipt": {
                        "status": "draft_prepared",
                        "captionFilled": True,
                        "captionTextLength": 42,
                        "imagePreviewReady": True,
                        "submitReady": True,
                    },
                }
            ],
        }

        summary = summarize_publish_smoke(report)

        self.assertIn("bilibili_dynamic", summary)
        self.assertIn("captionTextLength=42", summary)
        self.assertIn("submitReady=True", summary)


if __name__ == "__main__":
    unittest.main()
