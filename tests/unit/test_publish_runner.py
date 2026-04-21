from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNNERS = ROOT / "tests" / "runners"
if str(RUNNERS) not in sys.path:
    sys.path.insert(0, str(RUNNERS))

from publish_from_package_runner import resolve_publish_source


class PublishRunnerTests(unittest.TestCase):
    def test_resolve_publish_source_accepts_publish_input_file(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            publish_input_path = root / "00_publish_input.json"
            publish_input_path.write_text(
                '{"scenePremiseZh": "demo premise", "socialPostText": "demo text", "imagePath": "demo.png"}',
                encoding="utf-8",
            )

            publish_input, _, source_meta = resolve_publish_source(str(publish_input_path))

            self.assertEqual(publish_input["scenePremiseZh"], "demo premise")
            self.assertEqual(source_meta["sourceType"], "publish_input")

    def test_resolve_publish_source_accepts_run_dir(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "runtime" / "runs" / "demo_run"
            (run_dir / "creative").mkdir(parents=True)
            (run_dir / "social_post").mkdir(parents=True)
            (run_dir / "execution").mkdir(parents=True)
            (run_dir / "input").mkdir(parents=True)
            image_path = run_dir / "output.png"
            image_path.write_bytes(b"fake-image")

            (run_dir / "input" / "character_assets_snapshot.json").write_text(
                '{"subjectProfile": {"subject_id": "tsukimi_rion", "display_name_zh": "demo", "identity_zh": ["junior high school girl"], "appearance_zh": ["short black hair", "slim build"], "psychology_zh": ["sensitive", "curious"], "allowed_changes_zh": ["hair accessories may change"], "forbidden_drift_zh": ["do not mature the face or body ratio"], "notes_zh": []}}',
                encoding="utf-8",
            )
            (run_dir / "input" / "default_run_context.json").write_text(
                '{"runMode": "default", "nowLocal": "2026-04-07T18:30:00"}',
                encoding="utf-8",
            )
            (run_dir / "creative" / "05_creative_package.json").write_text(
                '{"worldDesign": {"scenePremiseZh": "demo premise", "worldSceneZh": "demo scene"}}',
                encoding="utf-8",
            )
            (run_dir / "social_post" / "01_social_post_package.json").write_text(
                '{"socialPostText": "demo social post"}',
                encoding="utf-8",
            )
            (run_dir / "execution" / "04_execution_package.json").write_text(
                f'{{"meta": {{"createdAt": "2026-04-07T18:30:00"}}, "imagePath": "{image_path.as_posix()}"}}',
                encoding="utf-8",
            )

            publish_input, default_run_context, source_meta = resolve_publish_source(str(run_dir))

            self.assertEqual(publish_input["scenePremiseZh"], "demo premise")
            self.assertEqual(publish_input["socialPostText"], "demo social post")
            self.assertEqual(default_run_context["runMode"], "default")
            self.assertEqual(source_meta["sourceType"], "run_dir")


if __name__ == "__main__":
    unittest.main()
