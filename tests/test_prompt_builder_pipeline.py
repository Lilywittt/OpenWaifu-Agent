from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from io_utils import read_json
from prompt_builder.pipeline import run_prompt_builder_pipeline
from runtime_layout import create_run_bundle


class PromptBuilderPipelineTests(unittest.TestCase):
    def test_prompt_builder_pipeline_uses_subject_profile_plus_three_design_outputs(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            prompts_dir = project_dir / "prompts" / "prompt_builder"
            prompts_dir.mkdir(parents=True)
            (prompts_dir / "image_prompt.md").write_text("template", encoding="utf-8")

            bundle = create_run_bundle(project_dir, "default", "prompt-builder-pipeline")
            character_assets = {
                "subjectProfile": {
                    "display_name_zh": "demo",
                    "allowed_changes_zh": ["clip"],
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
            ):
                prompt_package = run_prompt_builder_pipeline(
                    project_dir,
                    bundle,
                    {"runMode": "default", "nowLocal": "2026-04-07T11:00:00"},
                    character_assets,
                    creative_package,
                    project_dir / "config" / "creative_model.json",
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


if __name__ == "__main__":
    unittest.main()
