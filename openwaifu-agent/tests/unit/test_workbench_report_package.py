from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from io_utils import write_json
from reporting.package import build_workbench_report_package
from runtime_layout import runs_root
from studio.content_workbench_store import append_run_index_record


class WorkbenchReportPackageTests(unittest.TestCase):
    def test_build_package_prefers_run_detail_snapshot(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_dir = runs_root(project_dir) / "2026-04-24T11-00-00_run"
            output_dir = run_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            image_path = output_dir / "demo.png"
            image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            write_json(
                output_dir / "run_summary.json",
                {
                    "runId": run_dir.name,
                    "socialPostText": "完整社媒文案",
                    "generatedImagePath": str(image_path),
                },
            )
            append_run_index_record(
                project_dir,
                {
                    "status": "completed",
                    "runId": run_dir.name,
                    "runRoot": str(run_dir),
                    "summaryPath": str(output_dir / "run_summary.json"),
                    "request": {"sourceKind": "scene_draft_text", "endStage": "image"},
                },
            )
            record = {
                "runId": run_dir.name,
                "runRoot": str(run_dir),
                "generatedImagePath": str(image_path),
                "socialPostPreview": "预览文案",
                "sourceKind": "scene_draft_text",
                "endStage": "image",
            }

            package = build_workbench_report_package(project_dir, record)

        assert package is not None
        self.assertEqual(package["runId"], run_dir.name)
        self.assertEqual(package["socialPostText"], "完整社媒文案")
        self.assertEqual(Path(package["imagePath"]), image_path.resolve())


if __name__ == "__main__":
    unittest.main()

