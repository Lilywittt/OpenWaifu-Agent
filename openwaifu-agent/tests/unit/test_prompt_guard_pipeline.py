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
from prompt_guard.pipeline import build_prompt_guard_input, run_prompt_guard_pipeline
from runtime_layout import create_run_bundle


def _write_llm_profiles(project_dir: Path) -> None:
    write_json(
        project_dir / "config" / "llm_profiles.json",
        {
            "profiles": {
                "reasoner": {
                    "provider": "deepseek-openai-compatible",
                    "baseUrl": "https://api.deepseek.com",
                    "chatCompletionsPath": "/chat/completions",
                    "envName": "DEEPSEEK_API_KEY",
                    "model": "deepseek-reasoner",
                }
            },
            "stages": {
                "prompt_guard.default": "reasoner",
            },
        },
    )


class PromptGuardPipelineTests(unittest.TestCase):
    def test_build_prompt_guard_input_uses_prompt_scene_and_subject(self):
        prompt_package = {
            "positivePrompt": "solo girl, bookstore, reaching for a book",
            "negativePrompt": "bad hands, extra fingers",
        }
        world_design = {
            "scenePremiseZh": "旧书店午后",
            "worldSceneZh": "她站在高书架前，准备抽出一本旧书。",
        }
        subject_profile = {
            "subject_id": "shan_xiaoyi",
            "display_name_zh": "单小伊",
            "identity_zh": ["初中女生", "13岁", "少女感明确", "不允许成熟化"],
            "appearance_zh": ["黑色齐肩披肩细发", "小红发夹", "清瘦", "初中女生比例"],
            "psychology_zh": ["敏感细腻", "轻微内向"],
            "allowed_changes_zh": ["发饰可变"],
            "forbidden_drift_zh": ["不允许成熟化身体比例"],
            "notes_zh": [],
        }

        payload = build_prompt_guard_input(prompt_package, world_design, subject_profile)

        self.assertEqual(list(payload.keys()), ["promptPackage", "sceneDraft", "subjectProfile"])
        self.assertEqual(payload["promptPackage"]["positivePrompt"], prompt_package["positivePrompt"])
        self.assertEqual(payload["sceneDraft"]["scenePremiseZh"], "旧书店午后")
        self.assertEqual(payload["subjectProfile"]["display_name_zh"], "单小伊")

    def test_prompt_guard_pipeline_writes_review_and_final_prompt_package(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            prompt_dir = project_dir / "prompts" / "prompt_guard"
            prompt_dir.mkdir(parents=True)
            (prompt_dir / "review_and_patch_prompt.md").write_text("template", encoding="utf-8")
            _write_llm_profiles(project_dir)

            bundle = create_run_bundle(project_dir, "default", "prompt-guard")
            character_assets = {
                "subjectProfile": {
                    "subject_id": "shan_xiaoyi",
                    "display_name_zh": "单小伊",
                    "identity_zh": ["初中女生", "13岁", "少女感明确", "不允许成熟化"],
                    "appearance_zh": ["黑色齐肩披肩细发", "小红发夹", "清瘦", "初中女生比例"],
                    "psychology_zh": ["敏感细腻", "轻微内向"],
                    "allowed_changes_zh": ["发饰可变"],
                    "forbidden_drift_zh": ["不允许成熟化身体比例"],
                    "notes_zh": [],
                }
            }
            creative_package = {
                "worldDesign": {
                    "scenePremiseZh": "旧书店午后",
                    "worldSceneZh": "她抬手取书，动作自然稳定。",
                }
            }
            prompt_package = {
                "positivePrompt": "solo girl, bookstore, twisting torso, both hands holding book overhead",
                "negativePrompt": "bad hands, extra fingers",
            }

            with patch(
                "prompt_guard.pipeline.call_json_task",
                return_value={
                    "status": "revised",
                    "issues": ["原 prompt 的肢体占用有冲突"],
                    "changeSummary": "收敛手部动作并统一身体朝向",
                    "positivePrompt": "solo girl, bookstore, one hand reaching to shelf, balanced standing pose",
                    "negativePrompt": "bad hands, extra fingers",
                },
            ):
                final_prompt_package = run_prompt_guard_pipeline(
                    project_dir,
                    bundle,
                    {"runMode": "default"},
                    character_assets,
                    creative_package,
                    prompt_package,
                )

            input_snapshot = read_json(bundle.prompt_guard_dir / "00_prompt_guard_input.json")
            review_snapshot = read_json(bundle.prompt_guard_dir / "01_review_report.json")
            package_snapshot = read_json(bundle.prompt_guard_dir / "02_prompt_package.json")

        self.assertEqual(input_snapshot["sceneDraft"]["scenePremiseZh"], "旧书店午后")
        self.assertEqual(review_snapshot["status"], "revised")
        self.assertTrue(review_snapshot["changed"])
        self.assertEqual(review_snapshot["issues"], ["原 prompt 的肢体占用有冲突"])
        self.assertEqual(package_snapshot["reviewStatus"], "revised")
        self.assertTrue(package_snapshot["promptChanged"])
        self.assertEqual(package_snapshot["sourcePromptPackagePath"], str(bundle.prompt_builder_dir / "01_prompt_package.json"))
        self.assertEqual(
            final_prompt_package["positivePrompt"],
            "solo girl, bookstore, one hand reaching to shelf, balanced standing pose",
        )


if __name__ == "__main__":
    unittest.main()
