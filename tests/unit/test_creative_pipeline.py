from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from creative.pipeline import CreativeSocialSamplingError, run_creative_pipeline
from io_utils import read_json, read_text, write_json
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
                },
                "reasoner": {
                    "provider": "deepseek-openai-compatible",
                    "baseUrl": "https://api.deepseek.com",
                    "chatCompletionsPath": "/chat/completions",
                    "envName": "DEEPSEEK_API_KEY",
                    "model": "deepseek-reasoner",
                },
            },
            "stages": {
                "creative.social_signal_filter": "chat",
                "creative.world_design": "reasoner",
                "creative.environment_design": "chat",
                "creative.styling_design": "chat",
                "creative.action_design": "chat",
            },
        },
    )


class CreativePipelineTests(unittest.TestCase):
    def test_creative_pipeline_uses_scene_draft_plus_three_text_design_branches(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            prompts_dir = project_dir / "prompts" / "creative"
            prompts_dir.mkdir(parents=True)
            for prompt_name in (
                "social_signal_filter.md",
                "world_design.md",
                "environment_design.md",
                "styling_design.md",
                "action_design.md",
            ):
                (prompts_dir / prompt_name).write_text("template", encoding="utf-8")
            _write_llm_profiles(project_dir)

            bundle = create_run_bundle(project_dir, "default", "creative-pipeline")
            character_assets = {
                "subjectProfile": {
                    "subject_id": "demo_subject",
                    "display_name_zh": "demo",
                    "identity_zh": ["初中女生", "少女感明确"],
                    "appearance_zh": ["黑色齐肩发", "清瘦"],
                    "psychology_zh": ["敏感", "好奇心强"],
                    "allowed_changes_zh": ["允许增加临时红晕"],
                    "forbidden_drift_zh": ["不允许成熟化"],
                    "notes_zh": [],
                }
            }
            shortlist = {
                "sourceKey": "bangumi",
                "sourceZh": "Bangumi",
                "providerKey": "bangumi_anime",
                "providerZh": "Bangumi / 动画分区",
                "sampledSignalsZh": ["signal one", "signal two", "signal three"],
            }

            with patch("creative.pipeline.collect_social_trend_sample", return_value=shortlist), patch(
                "creative.pipeline.call_json_task",
                side_effect=[
                    {"selectedSignalId": "signal_02"},
                    {"scenePremiseZh": "demo premise", "worldSceneZh": "demo world"},
                ],
            ), patch(
                "creative.pipeline.call_text_task",
                side_effect=["environment text", "styling text", "action text"],
            ):
                creative_package = run_creative_pipeline(
                    project_dir,
                    bundle,
                    {"runMode": "default", "nowLocal": "2026-04-06T18:00:00"},
                    character_assets,
                )

            filter_input = read_json(bundle.creative_dir / "00_social_signal_filter_input.json")
            world_input = read_json(bundle.creative_dir / "01_world_design_input.json")
            environment_input = read_json(bundle.creative_dir / "02_environment_design_input.json")
            styling_input = read_json(bundle.creative_dir / "03_styling_design_input.json")
            action_input = read_json(bundle.creative_dir / "04_action_design_input.json")
            environment_output = read_text(bundle.creative_dir / "02_environment_design.md").strip()
            styling_output = read_text(bundle.creative_dir / "03_styling_design.md").strip()
            action_output = read_text(bundle.creative_dir / "04_action_design.md").strip()
            package_snapshot = read_json(bundle.creative_dir / "05_creative_package.json")

            self.assertEqual([item["id"] for item in filter_input["signalCandidates"]], ["signal_01", "signal_02", "signal_03"])
            self.assertEqual(world_input["socialSignalSample"]["sampledSignalsZh"], ["signal two"])
            self.assertEqual(environment_input["sceneDraft"]["scenePremiseZh"], "demo premise")
            self.assertEqual(styling_input["sceneDraft"]["scenePremiseZh"], "demo premise")
            self.assertEqual(action_input["sceneDraft"]["scenePremiseZh"], "demo premise")
            self.assertEqual(environment_output, "environment text")
            self.assertEqual(styling_output, "styling text")
            self.assertEqual(action_output, "action text")
            self.assertEqual(package_snapshot["socialSignalSample"]["sampledSignalsZh"], ["signal two"])
            self.assertEqual(creative_package["environmentDesign"], "environment text")
            self.assertEqual(creative_package["actionDesign"], "action text")

    def test_creative_pipeline_surfaces_clear_social_sampling_error(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            prompts_dir = project_dir / "prompts" / "creative"
            prompts_dir.mkdir(parents=True)
            for prompt_name in (
                "social_signal_filter.md",
                "world_design.md",
                "environment_design.md",
                "styling_design.md",
                "action_design.md",
            ):
                (prompts_dir / prompt_name).write_text("template", encoding="utf-8")
            _write_llm_profiles(project_dir)

            bundle = create_run_bundle(project_dir, "default", "creative-pipeline-error")
            character_assets = {
                "subjectProfile": {
                    "subject_id": "demo_subject",
                    "display_name_zh": "demo",
                    "identity_zh": ["初中女生", "少女感明确"],
                    "appearance_zh": ["黑色齐肩发", "清瘦"],
                    "psychology_zh": ["敏感", "好奇心强"],
                    "allowed_changes_zh": ["允许增加临时红晕"],
                    "forbidden_drift_zh": ["不允许成熟化"],
                    "notes_zh": [],
                }
            }

            with patch(
                "creative.pipeline.collect_social_trend_sample",
                side_effect=RuntimeError("transport error: <urlopen error timed out>"),
            ):
                with self.assertRaises(CreativeSocialSamplingError) as context:
                    run_creative_pipeline(
                        project_dir,
                        bundle,
                        {"runMode": "default", "nowLocal": "2026-04-06T18:00:00"},
                        character_assets,
                    )

            self.assertIn("实时社媒采样失败", str(context.exception))


if __name__ == "__main__":
    unittest.main()
