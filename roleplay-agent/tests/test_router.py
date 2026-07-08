from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from roleplay_agent.router import MODE_CHAT, MODE_IMAGE, interpret_message, save_user_state


class RouterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.user_id = "unit_router_user"
        state_path = PROJECT_DIR / "runtime" / "users" / f"{self.user_id}.json"
        if state_path.exists():
            state_path.unlink()

    def test_default_message_goes_to_chat(self) -> None:
        result = interpret_message(project_dir=PROJECT_DIR, user_id=self.user_id, content="晚上好")
        self.assertEqual(result.kind, "chat")
        self.assertEqual(result.next_mode, MODE_CHAT)
        self.assertEqual(result.payload["text"], "晚上好")

    def test_image_mode_requires_system_command_and_can_exit(self) -> None:
        enter = interpret_message(project_dir=PROJECT_DIR, user_id=self.user_id, content="系统指令")
        self.assertEqual(enter.kind, "enter_image_mode")
        self.assertEqual(enter.next_mode, MODE_IMAGE)
        save_user_state(PROJECT_DIR, self.user_id, mode=enter.next_mode, pending_action=enter.next_pending)

        generate = interpret_message(project_dir=PROJECT_DIR, user_id=self.user_id, content="生成")
        self.assertEqual(generate.kind, "image_generate")

        exit_result = interpret_message(project_dir=PROJECT_DIR, user_id=self.user_id, content="退出系统指令")
        self.assertEqual(exit_result.kind, "exit_image_mode")
        self.assertEqual(exit_result.next_mode, MODE_CHAT)


if __name__ == "__main__":
    unittest.main()
