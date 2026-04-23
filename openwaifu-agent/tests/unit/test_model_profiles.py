from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from io_utils import write_json
from model_profiles import list_model_profiles, list_stage_profile_map, resolve_stage_model_profile


def _write_llm_profiles(project_dir: Path) -> None:
    write_json(
        project_dir / "config" / "llm_profiles.json",
        {
            "profiles": {
                "chat": {"model": "deepseek-chat", "envName": "DEEPSEEK_API_KEY"},
                "reasoner": {"model": "deepseek-reasoner", "envName": "DEEPSEEK_API_KEY"},
            },
            "stages": {
                "creative.world_design": "reasoner",
                "prompt_guard.default": "reasoner",
                "social_post.default": "chat",
            },
        },
    )


class ModelProfilesTests(unittest.TestCase):
    def test_resolve_stage_model_profile_reads_unified_config(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            _write_llm_profiles(project_dir)

            profile = resolve_stage_model_profile(project_dir, "creative.world_design")

        self.assertEqual(profile["model"], "deepseek-reasoner")

    def test_list_helpers_return_unified_sections(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            _write_llm_profiles(project_dir)

            profiles = list_model_profiles(project_dir)
            stages = list_stage_profile_map(project_dir)

        self.assertEqual(set(profiles.keys()), {"chat", "reasoner"})
        self.assertEqual(stages["social_post.default"], "chat")

    def test_resolve_stage_model_profile_raises_clear_error_when_stage_missing(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            _write_llm_profiles(project_dir)

            with self.assertRaisesRegex(RuntimeError, "llm stage is not configured"):
                resolve_stage_model_profile(project_dir, "creative.action_design")


if __name__ == "__main__":
    unittest.main()
