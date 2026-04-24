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
from reporting.sources import capture_workbench_source_cursor, list_new_reportable_run_records
from runtime_layout import runs_root
from studio.content_workbench_store import append_run_index_record


class WorkbenchReportSourcesTests(unittest.TestCase):
    def test_cursor_only_emits_new_completed_runs_with_image_and_social_text(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            existing_run = runs_root(project_dir) / "2026-04-24T10-00-00_existing"
            existing_output = existing_run / "output"
            existing_output.mkdir(parents=True, exist_ok=True)
            existing_image = existing_output / "existing.png"
            existing_image.write_bytes(b"\x89PNG\r\n\x1a\n")
            write_json(
                existing_output / "run_summary.json",
                {
                    "runId": existing_run.name,
                    "socialPostText": "old report",
                    "generatedImagePath": str(existing_image),
                },
            )
            append_run_index_record(
                project_dir,
                {
                    "status": "completed",
                    "runId": existing_run.name,
                    "runRoot": str(existing_run),
                    "summaryPath": str(existing_output / "run_summary.json"),
                    "request": {"sourceKind": "scene_draft_text", "endStage": "image"},
                },
            )

            cursor = capture_workbench_source_cursor(project_dir)

            new_run = runs_root(project_dir) / "2026-04-24T10-05-00_new"
            new_output = new_run / "output"
            new_output.mkdir(parents=True, exist_ok=True)
            new_image = new_output / "new.png"
            new_image.write_bytes(b"\x89PNG\r\n\x1a\n")
            write_json(
                new_output / "run_summary.json",
                {
                    "runId": new_run.name,
                    "socialPostText": "new report",
                    "generatedImagePath": str(new_image),
                },
            )
            append_run_index_record(
                project_dir,
                {
                    "status": "completed",
                    "runId": new_run.name,
                    "runRoot": str(new_run),
                    "summaryPath": str(new_output / "run_summary.json"),
                    "request": {"sourceKind": "scene_draft_text", "endStage": "image"},
                },
            )

            failed_run = runs_root(project_dir) / "2026-04-24T10-06-00_failed"
            failed_output = failed_run / "output"
            failed_output.mkdir(parents=True, exist_ok=True)
            failed_image = failed_output / "failed.png"
            failed_image.write_bytes(b"\x89PNG\r\n\x1a\n")
            write_json(
                failed_output / "run_summary.json",
                {
                    "runId": failed_run.name,
                    "socialPostText": "should skip",
                    "generatedImagePath": str(failed_image),
                },
            )
            append_run_index_record(
                project_dir,
                {
                    "status": "failed",
                    "runId": failed_run.name,
                    "runRoot": str(failed_run),
                    "summaryPath": str(failed_output / "run_summary.json"),
                    "request": {"sourceKind": "scene_draft_text", "endStage": "image"},
                },
            )

            records, next_cursor = list_new_reportable_run_records(project_dir, cursor)

        self.assertEqual([record["runId"] for record in records], [new_run.name])
        self.assertEqual(next_cursor["lineCount"], 3)


if __name__ == "__main__":
    unittest.main()

