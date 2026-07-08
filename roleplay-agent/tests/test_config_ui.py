from __future__ import annotations

import sys
import tempfile
import unittest
from json import loads
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from roleplay_agent.character_catalog import (
    create_character,
    delete_character,
    load_character_catalog,
    purge_character,
    restore_character,
    trashed_characters,
    update_character_name,
)
from roleplay_agent.config_ui.server import build_prompt_preview, read_config_payload
from roleplay_agent.io_utils import ensure_dir, write_json


class ConfigUiTest(unittest.TestCase):
    def make_character_project(self, root: Path) -> None:
        ensure_dir(root / "config")
        ensure_dir(root / "characters")
        write_json(root / "config" / "characters.json", {"schemaVersion": 1, "activeCharacterId": "default", "order": ["default"]})
        write_json(
            root / "characters" / "default.json",
            {
                "schemaVersion": 1,
                "id": "default",
                "name": "默认角色",
                "sections": [],
                "metadata": {},
            },
        )

    def test_config_payload_exposes_prompt_inputs(self) -> None:
        payload = read_config_payload(PROJECT_DIR, user_id="unit_config_user")
        self.assertIn("character", payload)
        self.assertIn("characterCatalog", payload)
        self.assertIn("activeCharacterId", payload["characterCatalog"])
        self.assertIn("order", payload["characterCatalog"])
        self.assertIn("name", payload["character"])
        self.assertIn("sections", payload["character"])
        self.assertIn("persona", payload)
        self.assertIn("lorebook", payload)
        self.assertIn("events", payload)
        self.assertIn("systemTemplate", payload["prompts"])
        self.assertIn("post_history_instructions", payload["prompts"])

    def test_prompt_preview_shows_final_messages(self) -> None:
        preview = build_prompt_preview(
            PROJECT_DIR,
            user_id="unit_config_user",
            user_text="今天想聊一下 openwaifu 生图。",
        )
        messages = preview["messages"]
        self.assertGreaterEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("单小伊", messages[0]["content"])
        self.assertNotIn("openwaifu-agent", messages[0]["content"])
        self.assertEqual(messages[-1]["role"], "user")

    def test_character_actions_return_current_catalog_without_dirty_index(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            project_dir = Path(raw_dir)
            self.make_character_project(project_dir)

            created = create_character(project_dir, name="测试角色")
            created_id = created["activeCharacterId"]
            self.assertIn({"id": created_id, "name": "测试角色"}, created["items"])

            index_payload = loads((project_dir / "config" / "characters.json").read_text(encoding="utf-8-sig"))
            self.assertEqual(set(index_payload.keys()), {"schemaVersion", "activeCharacterId", "order"})
            self.assertNotIn("items", index_payload)

            renamed = update_character_name(project_dir, character_id=created_id, name="新名字")
            self.assertIn({"id": created_id, "name": "新名字"}, renamed["items"])

            deleted = delete_character(project_dir, created_id)
            self.assertEqual(deleted["activeCharacterId"], "default")
            self.assertNotIn(created_id, deleted["order"])
            self.assertFalse((project_dir / "characters" / f"{created_id}.json").exists())
            self.assertTrue((project_dir / "runtime" / "character_trash" / f"{created_id}.json").exists())
            self.assertEqual(trashed_characters(project_dir)[0]["id"], created_id)

            restored = restore_character(project_dir, created_id)
            self.assertEqual(restored["activeCharacterId"], created_id)
            self.assertIn(created_id, restored["order"])
            self.assertTrue((project_dir / "characters" / f"{created_id}.json").exists())
            self.assertFalse((project_dir / "runtime" / "character_trash" / f"{created_id}.json").exists())
            self.assertEqual(trashed_characters(project_dir), [])

            delete_character(project_dir, created_id)
            purged = purge_character(project_dir, created_id)
            self.assertFalse((project_dir / "characters" / f"{created_id}.json").exists())
            self.assertEqual(load_character_catalog(project_dir), purged)


if __name__ == "__main__":
    unittest.main()
