from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from io_utils import write_json
from model_profiles import resolve_creative_model_config_path, resolve_prompt_guard_model_config_path


class ModelProfilesTests(unittest.TestCase):
    def test_resolve_model_profile_paths_reads_configured_files(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            write_json(
                project_dir / "config" / "llm_profiles.json",
                {
                    "creativeModelConfigPath": "config/creative_model.json",
                    "promptGuardModelConfigPath": "config/prompt_guard_model.json",
                },
            )
            write_json(project_dir / "config" / "creative_model.json", {"model": "creative"})
            write_json(project_dir / "config" / "prompt_guard_model.json", {"model": "guard"})

            creative_path = resolve_creative_model_config_path(project_dir)
            prompt_guard_path = resolve_prompt_guard_model_config_path(project_dir)

        self.assertTrue(str(creative_path).endswith("config\\creative_model.json"))
        self.assertTrue(str(prompt_guard_path).endswith("config\\prompt_guard_model.json"))

    def test_resolve_model_profile_paths_raise_clear_error_when_missing(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)

            with self.assertRaisesRegex(RuntimeError, "llm profiles config does not exist"):
                resolve_creative_model_config_path(project_dir)


if __name__ == "__main__":
    unittest.main()
