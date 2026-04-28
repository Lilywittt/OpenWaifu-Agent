from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from io_utils import read_json, write_json
from prompt_builder.pipeline import run_prompt_builder_pipeline
from runtime_layout import create_run_bundle


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
                "prompt_builder.default": {"profile": "chat", "temperature": 0.7},
            },
        },
    )


class PromptBuilderPipelineTests(unittest.TestCase):
    def test_prompt_builder_pipeline_uses_subject_profile_plus_three_design_outputs(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            prompts_dir = project_dir / "prompts" / "prompt_builder"
            prompts_dir.mkdir(parents=True)
            (prompts_dir / "image_prompt.md").write_text("template", encoding="utf-8")
            _write_llm_profiles(project_dir)

            bundle = create_run_bundle(project_dir, "default", "prompt-builder-pipeline")
            character_assets = {
                "subjectProfile": {
                    "subject_id": "demo_subject",
                    "display_name_zh": "demo",
                    "identity_zh": ["初中女生", "少女感明确"],
                    "appearance_zh": ["黑色齐肩发", "小红发夹", "清瘦"],
                    "psychology_zh": ["敏感", "好奇心强"],
                    "allowed_changes_zh": ["clip"],
                    "forbidden_drift_zh": ["不允许成熟化"],
                    "notes_zh": [],
                }
            }
            creative_package = {
                "environmentDesign": "environment text",
                "stylingDesign": "styling text",
                "actionDesign": "action text",
            }

            with patch(
                "prompt_builder.pipeline.call_json_task",
                return_value={"positive": "positive prompt text", "negative": "negative prompt text"},
            ) as mocked_call:
                prompt_package = run_prompt_builder_pipeline(
                    project_dir,
                    bundle,
                    {"runMode": "default", "nowLocal": "2026-04-07T11:00:00"},
                    character_assets,
                    creative_package,
                )

            image_prompt_input = read_json(bundle.prompt_builder_dir / "00_image_prompt_input.json")
            image_prompt_output = read_json(bundle.prompt_builder_dir / "00_image_prompt.json")
            package_snapshot = read_json(bundle.prompt_builder_dir / "01_prompt_package.json")

            self.assertEqual(
                list(image_prompt_input.keys()),
                ["subjectProfile", "actionDesign", "stylingDesign", "environmentDesign"],
            )
            self.assertEqual(image_prompt_input["subjectProfile"]["display_name_zh"], "demo")
            self.assertEqual(image_prompt_input["subjectProfile"]["allowed_changes_zh"], ["clip"])
            self.assertEqual(image_prompt_input["actionDesign"], "action text")
            self.assertEqual(image_prompt_input["stylingDesign"], "styling text")
            self.assertEqual(image_prompt_input["environmentDesign"], "environment text")
            self.assertEqual(image_prompt_output["positive"], "positive prompt text")
            self.assertEqual(image_prompt_output["negative"], "negative prompt text")
            self.assertEqual(package_snapshot["positivePrompt"], "positive prompt text")
            self.assertEqual(package_snapshot["negativePrompt"], "negative prompt text")
            self.assertEqual(prompt_package["positivePrompt"], "positive prompt text")
            self.assertEqual(prompt_package["negativePrompt"], "negative prompt text")
            self.assertEqual(mocked_call.call_args.kwargs["model_config"]["temperature"], 0.7)


if __name__ == "__main__":
    unittest.main()
