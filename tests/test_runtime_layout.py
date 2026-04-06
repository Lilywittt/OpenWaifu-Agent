from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from runtime_layout import create_run_bundle


class RuntimeLayoutTests(unittest.TestCase):
    def test_create_run_bundle_uses_single_flat_run_package(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            bundle = create_run_bundle(project_dir, "default", "demo")
            self.assertTrue(bundle.input_dir.is_dir())
            self.assertTrue(bundle.creative_dir.is_dir())
            self.assertTrue(bundle.render_dir.is_dir())
            self.assertTrue(bundle.output_dir.is_dir())
            self.assertTrue(bundle.trace_dir.is_dir())
            self.assertTrue((bundle.root / "bundle.json").exists())


if __name__ == "__main__":
    unittest.main()
