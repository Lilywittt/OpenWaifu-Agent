from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from io_utils import read_json, read_text
from runtime_layout import create_run_bundle
from social_post.pipeline import run_social_post_pipeline


class SocialPostPipelineTests(unittest.TestCase):
    def test_social_post_pipeline_uses_subject_profile_plus_scene_draft_and_writes_output(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            prompts_dir = project_dir / "prompts" / "social_post"
            prompts_dir.mkdir(parents=True)

            bundle = create_run_bundle(project_dir, "default", "social-post-pipeline")
            character_assets = {
                "subjectProfile": {
                    "display_name_zh": "demo",
                }
            }
            creative_package = {
                "worldDesign": {
                    "scenePremiseZh": "demo premise",
                    "worldSceneZh": "demo scene",
                }
            }

            (prompts_dir / "social_post.md").write_text(
                "【人物资产】\n{{character_asset}}\n\n【场景设计稿】\n{{scene_design}}",
                encoding="utf-8",
            )

            with patch("social_post.pipeline.call_text_task", return_value="social post text") as mocked_call:
                social_post_package = run_social_post_pipeline(
                    project_dir,
                    bundle,
                    {"runMode": "default", "nowLocal": "2026-04-07T15:00:00"},
                    character_assets,
                    creative_package,
                    project_dir / "config" / "creative_model.json",
                )

            social_post_input = read_json(bundle.social_post_dir / "00_social_post_input.json")
            social_post_package_snapshot = read_json(bundle.social_post_dir / "01_social_post_package.json")
            social_post_output = read_text(bundle.social_post_dir / "00_social_post.txt").strip()
            final_output = read_text(bundle.output_dir / "social_post.txt").strip()
            call_kwargs = mocked_call.call_args.kwargs

            self.assertEqual(list(social_post_input.keys()), ["subjectProfile", "sceneDraft"])
            self.assertEqual(social_post_input["subjectProfile"]["display_name_zh"], "demo")
            self.assertEqual(social_post_input["sceneDraft"]["scenePremiseZh"], "demo premise")
            self.assertEqual(social_post_output, "social post text")
            self.assertEqual(final_output, "social post text")
            self.assertEqual(social_post_package_snapshot["socialPostText"], "social post text")
            self.assertEqual(social_post_package["sceneDraftPremiseZh"], "demo premise")
            self.assertIn("人物显示名", call_kwargs["system_prompt"])
            self.assertIn("demo premise", call_kwargs["system_prompt"])
            self.assertNotIn("{{character_asset}}", call_kwargs["system_prompt"])
            self.assertNotIn("{{scene_design}}", call_kwargs["system_prompt"])
            self.assertIsNone(call_kwargs["user_payload"])
            self.assertEqual(call_kwargs["temperature"], 1.6)


if __name__ == "__main__":
    unittest.main()
