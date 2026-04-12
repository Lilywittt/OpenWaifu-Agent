from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from character_assets import load_character_assets
from io_utils import write_json


class CharacterAssetsTests(unittest.TestCase):
    def test_load_character_assets_reads_subject_profile_from_configured_path(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            write_json(
                project_dir / "config" / "character_assets.json",
                {"subjectProfilePath": "character/subject_profile.json"},
            )
            write_json(
                project_dir / "character" / "subject_profile.json",
                {"subject_id": "shan_xiaoyi", "display_name_zh": "单小伊"},
            )

            character_assets = load_character_assets(project_dir)

        self.assertEqual(character_assets["subjectProfile"]["subject_id"], "shan_xiaoyi")

    def test_load_character_assets_raises_clear_error_when_configured_file_is_missing(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            write_json(
                project_dir / "config" / "character_assets.json",
                {"subjectProfilePath": "character/missing.json"},
            )

            with self.assertRaisesRegex(RuntimeError, "character subject profile does not exist"):
                load_character_assets(project_dir)


if __name__ == "__main__":
    unittest.main()
