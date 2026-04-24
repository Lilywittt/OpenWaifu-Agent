from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from io_utils import read_json, read_text, write_json
from runtime_layout import create_run_bundle
from social_post.pipeline import run_social_post_pipeline


def _subject_profile() -> dict:
    return {
        "subject_id": "demo_subject",
        "display_name_zh": "demo",
        "identity_zh": ["junior high school girl"],
        "appearance_zh": ["short black hair", "slim build"],
        "psychology_zh": ["sensitive", "curious"],
        "allowed_changes_zh": ["hair accessories may change"],
        "forbidden_drift_zh": ["do not mature the face or body ratio"],
        "notes_zh": [],
    }


def _write_llm_profiles(project_dir: Path) -> None:
    write_json(
        project_dir / "config" / "llm_profiles.json",
        {
            "profiles": {
                "chat": {
                    "provider": "deepseek-openai-compatible",
                    "baseUrl": "https://api.deepseek.com",
                    "chatCompletionsPath": "/chat/completions",
                    "envName": "DEEPSEEK_API_KEY",
                    "model": "deepseek-chat",
                }
            },
            "stages": {
                "social_post.default": "chat",
            },
        },
    )


class SocialPostPipelineTests(unittest.TestCase):
    def test_social_post_pipeline_uses_subject_profile_plus_scene_draft_and_writes_output(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            prompts_dir = project_dir / "prompts" / "social_post"
            prompts_dir.mkdir(parents=True)
            _write_llm_profiles(project_dir)

            bundle = create_run_bundle(project_dir, "default", "social-post-pipeline")
            character_assets = {"subjectProfile": _subject_profile()}
            creative_package = {
                "worldDesign": {
                    "scenePremiseZh": "demo premise",
                    "worldSceneZh": "demo scene",
                }
            }

            (prompts_dir / "social_post.md").write_text(
                "[character]\n{{character_asset}}\n\n[scene]\n{{scene_design}}",
                encoding="utf-8",
            )

            with patch("social_post.pipeline.call_text_task", return_value="social post text") as mocked_call:
                social_post_package = run_social_post_pipeline(
                    project_dir,
                    bundle,
                    {"runMode": "default", "nowLocal": "2026-04-07T15:00:00"},
                    character_assets,
                    creative_package,
                )

            social_post_input = read_json(bundle.social_post_dir / "00_social_post_input.json")
            social_post_package_snapshot = read_json(bundle.social_post_dir / "01_social_post_package.json")
            social_post_output = read_text(bundle.social_post_dir / "00_social_post.txt").strip()
            final_output = read_text(bundle.output_dir / "social_post.txt").strip()
            call_kwargs = mocked_call.call_args.kwargs

            self.assertEqual(list(social_post_input.keys()), ["subjectProfile", "sceneDraft"])
            self.assertEqual(social_post_input["subjectProfile"]["display_name_zh"], "demo")
            self.assertEqual(social_post_input["subjectProfile"]["identity_zh"], ["junior high school girl"])
            self.assertEqual(social_post_input["sceneDraft"]["scenePremiseZh"], "demo premise")
            self.assertEqual(social_post_output, "social post text")
            self.assertEqual(final_output, "social post text")
            self.assertEqual(social_post_package_snapshot["socialPostText"], "social post text")
            self.assertEqual(social_post_package["sceneDraftPremiseZh"], "demo premise")
            self.assertIn("demo", call_kwargs["system_prompt"])
            self.assertIn("demo premise", call_kwargs["system_prompt"])
            self.assertNotIn("{{character_asset}}", call_kwargs["system_prompt"])
            self.assertNotIn("{{scene_design}}", call_kwargs["system_prompt"])
            self.assertIsNone(call_kwargs["user_payload"])
            self.assertEqual(call_kwargs["temperature"], 1.1)
            self.assertEqual(call_kwargs["top_p"], 0.9)
            self.assertEqual(call_kwargs["top_k"], 50)


if __name__ == "__main__":
    unittest.main()
