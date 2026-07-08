from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from roleplay_agent.prompting import build_system_prompt, load_post_history_instructions


class PromptingTest(unittest.TestCase):
    def test_prompt_includes_editable_roleplay_context(self) -> None:
        bundle = build_system_prompt(
            PROJECT_DIR,
            user_id="unit_prompt_user",
            memory_summary="用户正在测试角色聊天服务。",
            context_text="我们聊一下生图和 openwaifu。",
        )
        self.assertIn("单小伊", bundle.system_prompt)
        self.assertNotIn("openwaifu-agent", bundle.system_prompt)
        self.assertNotIn("sourceProfilePath", bundle.system_prompt)
        self.assertIn("用户正在测试角色聊天服务。", bundle.system_prompt)
        self.assertNotIn("暂无长期记忆", bundle.system_prompt)
        self.assertIn("character", bundle.source_paths)
        self.assertIn("lorebook", bundle.source_paths)

    def test_post_history_instruction_is_editable_prompt_file(self) -> None:
        text = load_post_history_instructions(PROJECT_DIR)
        self.assertEqual(text, "")


if __name__ == "__main__":
    unittest.main()
