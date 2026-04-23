from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from publish.qq_bot_scene_draft import (
    MAX_SCENE_DRAFT_HISTORY_PER_USER,
    latest_scene_draft_path,
    parse_scene_draft_message,
    persist_scene_draft_message,
    qq_bot_scene_drafts_root,
)


class QQBotSceneDraftTests(unittest.TestCase):
    def test_parse_scene_draft_message_accepts_json(self):
        payload = parse_scene_draft_message(
            '{"scenePremiseZh":"便利店夜色","worldSceneZh":"夜里的便利店门口，主角提着塑料袋站在路灯下。"}'
        )

        self.assertEqual(payload["scenePremiseZh"], "便利店夜色")
        self.assertIn("便利店", payload["worldSceneZh"])

    def test_parse_scene_draft_message_rejects_missing_world_scene(self):
        with self.assertRaises(RuntimeError):
            parse_scene_draft_message('{"scenePremiseZh":"只有标题"}')

    def test_parse_scene_draft_message_accepts_plain_text(self):
        payload = parse_scene_draft_message("雨夜的书店门口，女孩抱着书站在屋檐下。")

        self.assertEqual(payload["scenePremiseZh"], "")
        self.assertIn("雨夜", payload["worldSceneZh"])

    def test_parse_scene_draft_message_accepts_json_with_only_world_scene(self):
        payload = parse_scene_draft_message('{"worldSceneZh":"午后的阁楼里，女孩翻开一本旧书。"}')

        self.assertEqual(payload["scenePremiseZh"], "")
        self.assertIn("阁楼", payload["worldSceneZh"])

    def test_persist_scene_draft_message_writes_runtime_cache(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            target_path = persist_scene_draft_message(
                project_dir,
                user_openid="user-demo",
                scene_draft={
                    "scenePremiseZh": "旧书店阁楼里的午后魔法",
                    "worldSceneZh": "阁楼里尘埃漂浮，主角踮脚抽书。",
                },
            )

        self.assertEqual(target_path.name, "latest.json")
        self.assertIn("runtime", str(target_path))
        self.assertIn("qq_bot_scene_drafts", str(target_path))

    def test_persist_scene_draft_message_updates_latest_and_history(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            target_path = persist_scene_draft_message(
                project_dir,
                user_openid="user-demo",
                scene_draft={
                    "scenePremiseZh": "旧书店阁楼里的午后魔法",
                    "worldSceneZh": "阁楼里尘埃漂浮，主角踮脚抽书。",
                },
            )

            cache_root = qq_bot_scene_drafts_root(project_dir)
            history_files = sorted(cache_root.glob("user-demo/history/*.json"))

            self.assertEqual(target_path, latest_scene_draft_path(project_dir, "user-demo"))
            self.assertTrue(target_path.exists())
            self.assertEqual(len(history_files), 1)

    def test_history_keeps_only_recent_entries_per_user(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            for index in range(MAX_SCENE_DRAFT_HISTORY_PER_USER + 3):
                persist_scene_draft_message(
                    project_dir,
                    user_openid="user-demo",
                    scene_draft={
                        "scenePremiseZh": f"场景 {index}",
                        "worldSceneZh": f"正文 {index}",
                    },
                )

            cache_root = qq_bot_scene_drafts_root(project_dir)
            history_files = sorted(cache_root.glob("user-demo/history/*.json"))

            self.assertEqual(len(history_files), MAX_SCENE_DRAFT_HISTORY_PER_USER)


if __name__ == "__main__":
    unittest.main()
