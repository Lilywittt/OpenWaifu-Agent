from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tests" / "runners"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from common import resolve_creative_package_paths, resolve_source_path_to_creative_package


class PromptExecutionRunnerTests(unittest.TestCase):
    def test_resolve_source_path_to_creative_package_accepts_run_dir_creative_dir_and_file(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "runtime" / "runs" / "demo_run"
            creative_dir = run_dir / "creative"
            creative_dir.mkdir(parents=True)
            package_path = creative_dir / "05_creative_package.json"
            package_path.write_text("{}", encoding="utf-8")

            self.assertEqual(resolve_source_path_to_creative_package(str(run_dir)), package_path.resolve())
            self.assertEqual(resolve_source_path_to_creative_package(str(creative_dir)), package_path.resolve())
            self.assertEqual(resolve_source_path_to_creative_package(str(package_path)), package_path.resolve())

    def test_resolve_creative_package_paths_accepts_source_batch(self):
        with TemporaryDirectory() as temp_dir:
            batch_dir = Path(temp_dir) / "creative_midstream_batch"
            package_path = batch_dir / "samples" / "01" / "creative" / "05_creative_package.json"
            package_path.parent.mkdir(parents=True)
            package_path.write_text("{}", encoding="utf-8")

            paths = resolve_creative_package_paths(
                sources=[],
                source_batch=str(batch_dir),
                count=1,
            )

            self.assertEqual(paths, [package_path.resolve()])


if __name__ == "__main__":
    unittest.main()
