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
                {
                    "subject_id": "shan_xiaoyi",
                    "display_name_zh": "单小伊",
                    "identity_zh": ["初中女生", "13岁", "少女感明确", "不允许成熟化"],
                    "appearance_zh": ["清稚的少女脸", "黑色齐肩披肩细发", "小红发夹", "清瘦"],
                    "psychology_zh": ["敏感细腻", "好奇心强"],
                    "allowed_changes_zh": ["允许增加红晕等临时状态"],
                    "forbidden_drift_zh": ["不允许成熟面孔"],
                    "notes_zh": [],
                },
            )

            character_assets = load_character_assets(project_dir)

        self.assertEqual(character_assets["subjectProfile"]["subject_id"], "shan_xiaoyi")
        self.assertEqual(character_assets["subjectProfile"]["identity_zh"][0], "初中女生")
        self.assertEqual(character_assets["subjectProfile"]["psychology_zh"][0], "敏感细腻")

    def test_load_character_assets_raises_clear_error_when_configured_file_is_missing(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            write_json(
                project_dir / "config" / "character_assets.json",
                {"subjectProfilePath": "character/missing.json"},
            )

            with self.assertRaisesRegex(RuntimeError, "character subject profile does not exist"):
                load_character_assets(project_dir)

    def test_load_character_assets_rejects_old_profile_shape(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            write_json(
                project_dir / "config" / "character_assets.json",
                {"subjectProfilePath": "character/subject_profile.json"},
            )
            write_json(
                project_dir / "character" / "subject_profile.json",
                {
                    "subject_id": "shan_xiaoyi",
                    "display_name_zh": "单小伊",
                    "identity_truth": {"life_stage_zh": "初中女生"},
                },
            )

            with self.assertRaisesRegex(RuntimeError, "uses legacy fields"):
                load_character_assets(project_dir)


if __name__ == "__main__":
    unittest.main()
