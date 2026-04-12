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

from test_pipeline import (
    END_STAGE_IMAGE,
    END_STAGE_PROMPT,
    SOURCE_KIND_SAMPLE_TEXT,
    SOURCE_KIND_CREATIVE_PACKAGE_TEXT,
    SOURCE_KIND_PROMPT_PACKAGE_TEXT,
    SOURCE_KIND_PROMPT_PACKAGE_FILE,
    SOURCE_KIND_SCENE_DRAFT_TEXT,
    execute_workbench_task_in_bundle,
    execute_workbench_task,
    validate_workbench_request,
)
from io_utils import write_json
from runtime_layout import RunBundle


class ContentWorkbenchRunnerTests(unittest.TestCase):
    def test_validate_prompt_package_request_rejects_non_image_end_stage(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            prompt_package_path = project_dir / "prompt_builder" / "01_prompt_package.json"
            prompt_package_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_package_path.write_text("{}", encoding="utf-8")

            with self.assertRaises(RuntimeError):
                validate_workbench_request(
                    project_dir,
                    {
                        "sourceKind": SOURCE_KIND_PROMPT_PACKAGE_FILE,
                        "endStage": END_STAGE_PROMPT,
                        "sourcePath": str(prompt_package_path),
                    },
                )

    def test_execute_scene_draft_text_to_prompt_writes_summary_and_calls_bundle_callback(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            callback_calls: list[tuple[str, str]] = []

            def remember_bundle(bundle, normalized_request):
                callback_calls.append((bundle.run_id, normalized_request["sourceKind"]))

            def fake_prompt_guard_pipeline(_project_dir, bundle, *_args, **_kwargs):
                payload = {
                    "positivePrompt": "p1",
                    "negativePrompt": "n1",
                    "reviewStatus": "revised",
                    "promptChanged": True,
                    "reviewIssues": ["pose conflict"],
                    "changeSummary": "tightened pose",
                }
                write_json(bundle.prompt_guard_dir / "02_prompt_package.json", payload)
                return payload

            with patch("test_pipeline.core.load_character_assets", return_value={"subjectProfile": {"name": "单小伊"}}), patch(
                "test_pipeline.core.build_default_run_context",
                return_value={"createdAt": "2026-04-11T22:00:00"},
            ), patch(
                "test_pipeline.core.run_parallel_design_stages",
                return_value={
                    "environmentDesign": "环境设计",
                    "stylingDesign": "造型设计",
                    "actionDesign": "动作设计",
                },
            ), patch(
                "test_pipeline.core.run_social_post_pipeline",
                return_value={"socialPostText": "社媒文案"},
            ), patch(
                "test_pipeline.core.run_prompt_builder_pipeline",
                return_value={"positivePrompt": "p0", "negativePrompt": "n0"},
            ), patch(
                "test_pipeline.core.run_prompt_guard_pipeline",
                side_effect=fake_prompt_guard_pipeline,
            ), patch(
                "test_pipeline.core.resolve_creative_model_config_path",
                return_value=project_dir / "creative_model.json",
            ), patch(
                "test_pipeline.core.resolve_prompt_guard_model_config_path",
                return_value=project_dir / "prompt_guard_model.json",
            ), patch(
                "test_pipeline.core.occupy_generation_slot",
                return_value=nullcontext(),
            ) as slot_mock:
                result = execute_workbench_task(
                    project_dir,
                    {
                        "sourceKind": SOURCE_KIND_SCENE_DRAFT_TEXT,
                        "endStage": END_STAGE_PROMPT,
                        "label": "bench_prompt",
                        "sceneDraftText": "夜里便利店里，她刚看完动画，坐在窗边发呆。",
                    },
                    on_bundle_created=remember_bundle,
                )

                self.assertEqual(result["request"]["sourceKind"], SOURCE_KIND_SCENE_DRAFT_TEXT)
                self.assertTrue(slot_mock.called)
                self.assertEqual(result["summary"]["positivePromptText"], "p1")
                self.assertEqual(result["summary"]["promptReviewStatus"], "revised")
                self.assertTrue(result["summary"]["promptChanged"])
                self.assertTrue(callback_calls)
                self.assertEqual(callback_calls[0][1], SOURCE_KIND_SCENE_DRAFT_TEXT)
                self.assertTrue((result["bundle"].output_dir / "run_summary.json").is_file())
                self.assertTrue((result["bundle"].prompt_guard_dir / "02_prompt_package.json").is_file())

    def test_validate_sample_text_request_accepts_inline_content(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            payload = validate_workbench_request(
                project_dir,
                {
                    "sourceKind": SOURCE_KIND_SAMPLE_TEXT,
                    "endStage": END_STAGE_PROMPT,
                    "label": "sample_inline",
                    "sourceContent": "第一条采样\n第二条采样",
                },
            )
        self.assertEqual(payload["sourceKind"], SOURCE_KIND_SAMPLE_TEXT)
        self.assertIn("第一条采样", payload["sourceContent"])

    def test_validate_request_preserves_request_id(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            payload = validate_workbench_request(
                project_dir,
                {
                    "sourceKind": SOURCE_KIND_SCENE_DRAFT_TEXT,
                    "endStage": END_STAGE_PROMPT,
                    "label": "request_id_check",
                    "sceneDraftText": "夜里便利店",
                    "requestId": "req-123",
                },
            )
        self.assertEqual(payload["requestId"], "req-123")

    def test_validate_creative_package_text_requires_world_scene(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            with self.assertRaises(RuntimeError):
                validate_workbench_request(
                    project_dir,
                    {
                        "sourceKind": SOURCE_KIND_CREATIVE_PACKAGE_TEXT,
                        "endStage": END_STAGE_PROMPT,
                        "label": "creative_inline",
                        "worldSceneText": "",
                    },
                )

    def test_validate_prompt_package_text_requires_positive_and_negative(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            with self.assertRaises(RuntimeError):
                validate_workbench_request(
                    project_dir,
                    {
                        "sourceKind": SOURCE_KIND_PROMPT_PACKAGE_TEXT,
                        "endStage": END_STAGE_IMAGE,
                        "label": "prompt_inline",
                        "positivePromptText": "only positive",
                        "negativePromptText": "",
                    },
                )

    def test_execute_scene_draft_text_into_existing_bundle(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_root = project_dir / "runtime" / "test_batches" / "shared_core" / "samples" / "01"
            bundle = RunBundle(
                run_id="shared_core_sample01",
                root=run_root,
                input_dir=run_root / "input",
                creative_dir=run_root / "creative",
                social_post_dir=run_root / "social_post",
                prompt_builder_dir=run_root / "prompt_builder",
                prompt_guard_dir=run_root / "prompt_guard",
                execution_dir=run_root / "execution",
                publish_dir=run_root / "publish",
                output_dir=run_root / "output",
                trace_dir=run_root / "trace",
            )
            for path in (
                bundle.root,
                bundle.input_dir,
                bundle.creative_dir,
                bundle.social_post_dir,
                bundle.prompt_builder_dir,
                bundle.prompt_guard_dir,
                bundle.execution_dir,
                bundle.publish_dir,
                bundle.output_dir,
                bundle.trace_dir,
            ):
                path.mkdir(parents=True, exist_ok=True)

            with patch("test_pipeline.core.load_character_assets", return_value={"subjectProfile": {"name": "单小伊"}}), patch(
                "test_pipeline.core.build_default_run_context",
                return_value={"createdAt": "2026-04-12T10:00:00"},
            ), patch(
                "test_pipeline.core.run_parallel_design_stages",
                return_value={
                    "environmentDesign": "环境设计",
                    "stylingDesign": "造型设计",
                    "actionDesign": "动作设计",
                },
            ), patch(
                "test_pipeline.core.run_social_post_pipeline",
                return_value={"socialPostText": "社媒文案"},
            ), patch(
                "test_pipeline.core.run_prompt_builder_pipeline",
                return_value={"positivePrompt": "builder positive", "negativePrompt": "builder negative"},
            ), patch(
                "test_pipeline.core.run_prompt_guard_pipeline",
                return_value={
                    "positivePrompt": "guarded positive",
                    "negativePrompt": "guarded negative",
                    "reviewStatus": "revised",
                    "promptChanged": True,
                    "reviewIssues": ["pose conflict"],
                    "changeSummary": "tightened pose",
                },
            ), patch(
                "test_pipeline.core.run_execution_pipeline",
                return_value={"imagePath": str(bundle.output_dir / "image.png")},
            ), patch(
                "test_pipeline.core.resolve_creative_model_config_path",
                return_value=project_dir / "creative_model.json",
            ), patch(
                "test_pipeline.core.resolve_prompt_guard_model_config_path",
                return_value=project_dir / "prompt_guard_model.json",
            ), patch(
                "test_pipeline.core.occupy_generation_slot",
                return_value=nullcontext(),
            ):
                result = execute_workbench_task_in_bundle(
                    project_dir,
                    bundle,
                    {
                        "sourceKind": SOURCE_KIND_SCENE_DRAFT_TEXT,
                        "endStage": END_STAGE_IMAGE,
                        "label": "existing_bundle",
                        "sceneDraftText": "夜里便利店里，她抬头看着货架边缘。",
                    },
                )
                self.assertEqual(result["bundle"].root, run_root)
                self.assertEqual(result["summary"]["positivePromptText"], "guarded positive")
                self.assertTrue((bundle.output_dir / "run_summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
