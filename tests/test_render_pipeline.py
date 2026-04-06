from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from io_utils import write_json
from render.packet import build_render_packet
from render.prompt_compiler import assemble_prompt_bundle_from_cues
from runtime_layout import create_run_bundle


class RenderPipelineTests(unittest.TestCase):
    def test_render_packet_orders_hero_facts_first(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            (project_dir / "config").mkdir(parents=True)
            write_json(
                project_dir / "config" / "runtime_profile.json",
                {
                    "renderPromptPolicyPath": "./config/render_prompt_policy.json",
                    "defaultProvider": "comfyui-local-anime",
                },
            )
            write_json(
                project_dir / "config" / "render_prompt_policy.json",
                {
                    "stylePositiveEn": ["anime illustration"],
                    "genericNegativeEn": ["adult woman"],
                },
            )
            bundle = create_run_bundle(project_dir, "default", "test")
            render_blueprint = {
                "summaryZh": "summer beach spike",
                "subject": {
                    "identityReadZh": "young middle-school girl",
                    "facts": [
                        {"id": "subject_age", "textZh": "middle-school age read"},
                        {"id": "subject_marker", "textZh": "small red hair clip"},
                    ],
                    "forbidden": [{"id": "subject_no_adult", "textZh": "adult face"}],
                },
                "world": {
                    "summaryZh": "beach court",
                    "facts": [{"id": "world_place", "textZh": "seaside volleyball court"}],
                    "forbidden": [{"id": "world_no_school", "textZh": "school hallway"}],
                },
                "action": {
                    "summaryZh": "spike moment",
                    "facts": [{"id": "action_spike", "textZh": "jumping spike contact"}],
                    "forbidden": [{"id": "action_no_static", "textZh": "standing still"}],
                },
                "wardrobe": {
                    "summaryZh": "bikini outfit",
                    "required": [{"id": "wardrobe_bikini", "textZh": "bikini swimwear"}],
                    "optional": [{"id": "wardrobe_wind", "textZh": "light wind layer"}],
                    "forbidden": [{"id": "wardrobe_no_blazer", "textZh": "school blazer"}],
                },
                "camera": {
                    "summaryZh": "full body sports shot",
                    "framing": "full_body",
                    "aspectRatio": "4:5",
                    "facts": [{"id": "camera_full_body", "textZh": "full-body framing"}],
                    "forbidden": [{"id": "camera_no_crop", "textZh": "cropped legs"}],
                },
                "integration": {
                    "heroFactIds": ["camera_full_body", "action_spike", "subject_age"],
                    "supportingFactIds": ["wardrobe_bikini", "world_place", "subject_marker"],
                    "negativeFactIds": ["subject_no_adult", "wardrobe_no_blazer"],
                    "conflictResolutionsZh": [],
                    "renderIntentZh": "prioritize body readability and age read",
                },
            }
            render_packet = build_render_packet(project_dir, bundle, render_blueprint)
            self.assertEqual(render_packet["positiveFacts"][0]["id"], "camera_full_body")
            self.assertEqual(render_packet["positiveFacts"][1]["id"], "action_spike")
            self.assertEqual(render_packet["negativeFacts"][0]["id"], "subject_no_adult")

    def test_prompt_assembly_keeps_all_fact_ids_covered(self):
        render_packet = {
            "positiveFacts": [
                {"id": "subject_age", "section": "subject", "textZh": "middle-school age read"},
                {"id": "action_spike", "section": "action", "textZh": "jumping spike contact"},
            ],
            "negativeFacts": [
                {"id": "subject_no_adult", "section": "subject_forbidden", "textZh": "adult face"},
            ],
            "stylePositiveEn": ["anime illustration"],
            "genericNegativeEn": ["adult woman"],
        }
        prompt_bundle = assemble_prompt_bundle_from_cues(
            render_packet,
            positive_cues=[
                {"id": "subject_age", "phraseEn": "young middle-school girl"},
            ],
            negative_cues=[],
            notes_zh=["missing action cue should fall back to source fact"],
        )
        self.assertIn("young middle-school girl", prompt_bundle["positivePrompt"])
        self.assertIn("jumping spike contact", prompt_bundle["positivePrompt"])
        self.assertIn("adult face", prompt_bundle["negativePrompt"])
        self.assertIn("adult woman", prompt_bundle["negativePrompt"])


if __name__ == "__main__":
    unittest.main()
