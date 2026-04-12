from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from contextlib import nullcontext
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from io_utils import read_json
from product_pipeline import run_generation_product_pipeline
from runtime_layout import create_run_bundle


class ProductPipelineTests(unittest.TestCase):
    def test_generation_pipeline_uses_guarded_prompt_for_execution(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            bundle = create_run_bundle(project_dir, "default", "guarded-generation")
            character_assets = {"subjectProfile": {"display_name_zh": "单小伊"}}
            default_run_context = {"runMode": "default", "nowLocal": "2026-04-11T18:00:00"}
            creative_package = {
                "worldDesign": {
                    "scenePremiseZh": "旧书店午后",
                    "worldSceneZh": "她在旧书店里取下一本高处的书。",
                },
                "environmentDesign": "env",
                "stylingDesign": "style",
                "actionDesign": "action",
            }
            social_post_package = {"socialPostText": "今天像是翻开了一本积灰的旧书。"}
            prompt_builder_package = {
                "positivePrompt": "builder positive",
                "negativePrompt": "builder negative",
            }
            prompt_package = {
                "positivePrompt": "guarded positive",
                "negativePrompt": "guarded negative",
                "reviewStatus": "revised",
                "promptChanged": True,
                "reviewIssues": ["pose conflict"],
                "changeSummary": "tightened pose wording",
            }
            execution_package = {
                "imagePath": str(bundle.output_dir / "demo.png"),
                "checkpointName": "animagine-xl-4.0-opt.safetensors",
            }

            with (
                patch("product_pipeline.load_character_assets", return_value=character_assets),
                patch("product_pipeline.build_default_run_context", return_value=default_run_context),
                patch("product_pipeline.resolve_creative_model_config_path", return_value=project_dir / "config" / "creative_model.json"),
                patch("product_pipeline.resolve_prompt_guard_model_config_path", return_value=project_dir / "config" / "prompt_guard_model.json"),
                patch("product_pipeline.run_creative_pipeline", return_value=creative_package),
                patch("product_pipeline.run_social_post_pipeline", return_value=social_post_package),
                patch("product_pipeline.run_prompt_builder_pipeline", return_value=prompt_builder_package),
                patch("product_pipeline.run_prompt_guard_pipeline", return_value=prompt_package),
                patch("product_pipeline.run_execution_pipeline", return_value=execution_package) as execution_mock,
                patch("product_pipeline.occupy_generation_slot", return_value=nullcontext()) as slot_mock,
            ):
                result = run_generation_product_pipeline(project_dir, bundle)

            summary = read_json(bundle.output_dir / "run_summary.json")

        self.assertTrue(slot_mock.called)
        self.assertEqual(execution_mock.call_args.args[3], prompt_package)
        self.assertEqual(result["promptBuilderPackage"], prompt_builder_package)
        self.assertEqual(result["promptPackage"], prompt_package)
        self.assertEqual(summary["promptBuilderPackagePath"], str(bundle.prompt_builder_dir / "01_prompt_package.json"))
        self.assertEqual(summary["promptPackagePath"], str(bundle.prompt_guard_dir / "02_prompt_package.json"))
        self.assertEqual(summary["promptGuardReportPath"], str(bundle.prompt_guard_dir / "01_review_report.json"))
        self.assertEqual(summary["positivePromptText"], "guarded positive")
        self.assertEqual(summary["promptReviewStatus"], "revised")
        self.assertTrue(summary["promptChanged"])
        self.assertEqual(summary["promptReviewIssues"], ["pose conflict"])


if __name__ == "__main__":
    unittest.main()
