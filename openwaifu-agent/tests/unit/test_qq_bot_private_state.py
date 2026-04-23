from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from publish.qq_bot_private_state import (
    PENDING_ACTION_SCENE_DRAFT,
    clear_private_user_pending_action,
    load_private_user_state,
    set_private_user_mode,
    set_private_user_pending_action,
)
from publish.qq_bot_private_ui import MODE_DEVELOPER, MODE_EXPERIENCE


class QQBotPrivateStateTests(unittest.TestCase):
    def test_load_state_defaults_to_experience_mode(self):
        with TemporaryDirectory() as temp_dir:
            state = load_private_user_state(Path(temp_dir), "user-1")

        self.assertEqual(state["mode"], MODE_EXPERIENCE)
        self.assertEqual(state["pendingAction"], "")

    def test_set_mode_clears_pending_action(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            set_private_user_pending_action(project_dir, "user-1", PENDING_ACTION_SCENE_DRAFT)
            state = set_private_user_mode(project_dir, "user-1", MODE_DEVELOPER)

        self.assertEqual(state["mode"], MODE_DEVELOPER)
        self.assertEqual(state["pendingAction"], "")

    def test_pending_action_roundtrip(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            set_private_user_pending_action(project_dir, "user-1", PENDING_ACTION_SCENE_DRAFT)
            state = load_private_user_state(project_dir, "user-1")
            self.assertEqual(state["pendingAction"], PENDING_ACTION_SCENE_DRAFT)
            cleared = clear_private_user_pending_action(project_dir, "user-1")

        self.assertEqual(cleared["pendingAction"], "")


if __name__ == "__main__":
    unittest.main()
