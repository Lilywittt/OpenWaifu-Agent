from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNNERS = ROOT / "tests" / "runners"
if str(RUNNERS) not in sys.path:
    sys.path.insert(0, str(RUNNERS))

from runner_common import (
    create_sample_bundle,
    resolve_scene_draft_paths,
    resolve_source_path_to_scene_draft,
    resolve_source_path_to_world_design_input,
    resolve_world_design_input_paths,
)


class RunnerCommonTests(unittest.TestCase):
    def test_create_sample_bundle_matches_current_run_bundle_schema(self):
        with TemporaryDirectory() as temp_dir:
            sample_root = Path(temp_dir) / "batch" / "samples" / "01"
            bundle = create_sample_bundle(sample_root, 1)

            self.assertTrue(bundle.input_dir.is_dir())
            self.assertTrue(bundle.prompt_guard_dir.is_dir())
            self.assertTrue((bundle.root / "bundle.json").is_file())

    def test_resolve_source_path_to_world_design_input_accepts_run_dir_creative_dir_and_file(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "runtime" / "runs" / "demo_run"
            creative_dir = run_dir / "creative"
            creative_dir.mkdir(parents=True)
            input_path = creative_dir / "01_world_design_input.json"
            input_path.write_text("{}", encoding="utf-8")

            self.assertEqual(resolve_source_path_to_world_design_input(str(run_dir)), input_path.resolve())
            self.assertEqual(resolve_source_path_to_world_design_input(str(creative_dir)), input_path.resolve())
            self.assertEqual(resolve_source_path_to_world_design_input(str(input_path)), input_path.resolve())

    def test_resolve_world_design_input_paths_accepts_source_batch(self):
        with TemporaryDirectory() as temp_dir:
            batch_dir = Path(temp_dir) / "sample_batch"
            input_path = batch_dir / "samples" / "01" / "creative" / "01_world_design_input.json"
            input_path.parent.mkdir(parents=True)
            input_path.write_text("{}", encoding="utf-8")

            paths = resolve_world_design_input_paths(
                sources=[],
                source_batch=str(batch_dir),
                count=1,
            )

            self.assertEqual(paths, [input_path.resolve()])

    def test_resolve_source_path_to_scene_draft_accepts_run_dir_creative_dir_and_file(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "runtime" / "runs" / "demo_run"
            creative_dir = run_dir / "creative"
            creative_dir.mkdir(parents=True)
            scene_path = creative_dir / "01_world_design.json"
            scene_path.write_text("{}", encoding="utf-8")

            self.assertEqual(resolve_source_path_to_scene_draft(str(run_dir)), scene_path.resolve())
            self.assertEqual(resolve_source_path_to_scene_draft(str(creative_dir)), scene_path.resolve())
            self.assertEqual(resolve_source_path_to_scene_draft(str(scene_path)), scene_path.resolve())

    def test_resolve_scene_draft_paths_accepts_source_batch(self):
        with TemporaryDirectory() as temp_dir:
            batch_dir = Path(temp_dir) / "scene_batch"
            scene_path = batch_dir / "samples" / "01" / "creative" / "01_world_design.json"
            scene_path.parent.mkdir(parents=True)
            scene_path.write_text("{}", encoding="utf-8")

            paths = resolve_scene_draft_paths(
                sources=[],
                source_batch=str(batch_dir),
                count=1,
            )

            self.assertEqual(paths, [scene_path.resolve()])


if __name__ == "__main__":
    unittest.main()
