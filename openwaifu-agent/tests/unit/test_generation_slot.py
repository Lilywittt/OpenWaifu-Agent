from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from generation_slot import GenerationSlotBusyError, occupy_generation_slot, read_generation_slot


class GenerationSlotTests(unittest.TestCase):
    def test_slot_is_visible_while_held_and_cleared_on_release(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            self.assertIsNone(read_generation_slot(project_dir))
            with occupy_generation_slot(
                project_dir,
                owner_type="content_workbench",
                owner_label="night_store",
                run_id="run-001",
            ):
                holder = read_generation_slot(project_dir)
                self.assertIsNotNone(holder)
                self.assertEqual(holder["ownerType"], "content_workbench")
                self.assertEqual(holder["runId"], "run-001")
                self.assertIn("内容测试工作台", holder["busyMessage"])
            self.assertIsNone(read_generation_slot(project_dir))

    def test_second_acquire_raises_busy_error(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            with occupy_generation_slot(
                project_dir,
                owner_type="run_product",
                owner_label="run_product.py",
                run_id="run-001",
            ):
                with self.assertRaises(GenerationSlotBusyError) as ctx:
                    with occupy_generation_slot(
                        project_dir,
                        owner_type="content_workbench",
                        owner_label="night_store",
                        run_id="run-002",
                    ):
                        pass
        self.assertIn("本机当前正被", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
