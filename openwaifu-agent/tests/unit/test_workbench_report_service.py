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
from reporting.service import poll_workbench_report_once
from reporting.sources import capture_workbench_source_cursor
from reporting.state import read_sent_report_records
from runtime_layout import runs_root
from studio.content_workbench_store import append_run_index_record


class WorkbenchReportServiceTests(unittest.TestCase):
    def test_poll_once_only_reports_runs_created_after_service_started(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            old_run = runs_root(project_dir) / "2026-04-24T12-00-00_old"
            old_output = old_run / "output"
            old_output.mkdir(parents=True, exist_ok=True)
            old_image = old_output / "old.png"
            old_image.write_bytes(b"\x89PNG\r\n\x1a\n")
            write_json(
                old_output / "run_summary.json",
                {
                    "runId": old_run.name,
                    "socialPostText": "旧文案",
                    "generatedImagePath": str(old_image),
                },
            )
            append_run_index_record(
                project_dir,
                {
                    "status": "completed",
                    "runId": old_run.name,
                    "runRoot": str(old_run),
                    "summaryPath": str(old_output / "run_summary.json"),
                    "request": {"sourceKind": "scene_draft_text", "endStage": "image"},
                },
            )

            cursor = capture_workbench_source_cursor(project_dir)
            sent_payloads: list[dict] = []

            def fake_send_report(*, project_dir: Path, target_config: dict, report_package: dict) -> dict:
                sent_payloads.append(report_package)
                return {
                    "adapter": "qq_report",
                    "status": "sent",
                    "runId": report_package["runId"],
                    "messageId": "msg-demo",
                }

            cursor, first_stats = poll_workbench_report_once(
                project_dir,
                source_cursor=cursor,
                sent_run_ids=set(),
                target_config={"scene": "user"},
                log=lambda _message: None,
                send_report=fake_send_report,
            )

            new_run = runs_root(project_dir) / "2026-04-24T12-05-00_new"
            new_output = new_run / "output"
            new_output.mkdir(parents=True, exist_ok=True)
            new_image = new_output / "new.png"
            new_image.write_bytes(b"\x89PNG\r\n\x1a\n")
            write_json(
                new_output / "run_summary.json",
                {
                    "runId": new_run.name,
                    "socialPostText": "新文案",
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

            sent_run_ids: set[str] = set()
            cursor, second_stats = poll_workbench_report_once(
                project_dir,
                source_cursor=cursor,
                sent_run_ids=sent_run_ids,
                target_config={"scene": "user"},
                log=lambda _message: None,
                send_report=fake_send_report,
            )

            sent_records = read_sent_report_records(project_dir)

        self.assertEqual(first_stats["reported"], 0)
        self.assertEqual(second_stats["reported"], 1)
        self.assertEqual([payload["runId"] for payload in sent_payloads], [new_run.name])
        self.assertEqual([record["runId"] for record in sent_records], [new_run.name])


if __name__ == "__main__":
    unittest.main()
