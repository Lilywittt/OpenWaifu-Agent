from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from io_utils import write_json, write_text
from runtime_layout import runs_root
from studio.content_workbench_store import (
    append_run_index_record,
    build_content_workbench_snapshot,
    generate_cleanup_report,
    migrate_legacy_content_workbench_state,
    normalize_stale_workbench_status,
    reconcile_workbench_runtime_state,
    write_active_worker,
    workbench_inventory_paths,
    write_last_request,
    write_workbench_status,
)


class ContentWorkbenchStoreTests(unittest.TestCase):
    def test_build_snapshot_reads_status_history_last_request_and_run_detail(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            (project_dir / ".env").write_text("QQ_BOT_DISPLAY_NAME=单小伊 Agent\n", encoding="utf-8")
            run_dir = runs_root(project_dir) / "2026-04-11T20-00-00_content_workbench"
            creative_dir = run_dir / "creative"
            output_dir = run_dir / "output"
            prompt_guard_dir = run_dir / "prompt_guard"
            creative_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)
            prompt_guard_dir.mkdir(parents=True, exist_ok=True)
            image_path = output_dir / "demo.png"
            image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            write_json(
                creative_dir / "01_world_design.json",
                {"scenePremiseZh": "夜便利店", "worldSceneZh": "她坐在窗边看着雨幕。"},
            )
            write_text(creative_dir / "02_environment_design.md", "环境设计")
            write_text(creative_dir / "03_styling_design.md", "造型设计")
            write_text(creative_dir / "04_action_design.md", "动作设计")
            write_json(
                prompt_guard_dir / "02_prompt_package.json",
                {
                    "positivePrompt": "balanced pose",
                    "negativePrompt": "bad hands",
                    "reviewStatus": "approved",
                },
            )
            write_json(
                output_dir / "run_summary.json",
                {
                    "runId": run_dir.name,
                    "sceneDraftPremiseZh": "夜便利店",
                    "socialPostText": "今天的便利店灯光有点像动画片尾。",
                    "generatedImagePath": str(image_path),
                },
            )
            write_last_request(
                project_dir,
                {
                    "sourceKind": "scene_draft_text",
                    "endStage": "prompt",
                    "label": "night_store",
                    "sceneDraftText": "夜里便利店",
                },
            )
            write_workbench_status(
                project_dir,
                {
                    "status": "completed",
                    "stage": "测试完成",
                    "runId": run_dir.name,
                    "runRoot": str(run_dir),
                    "request": {"sourceKind": "scene_draft_text", "endStage": "prompt", "label": "night_store"},
                },
            )
            append_run_index_record(
                project_dir,
                {
                    "status": "completed",
                    "runId": run_dir.name,
                    "runRoot": str(run_dir),
                    "summaryPath": str(output_dir / "run_summary.json"),
                    "sceneDraftPremiseZh": "夜便利店",
                    "request": {"sourceKind": "scene_draft_text", "endStage": "prompt", "label": "night_store"},
                },
            )

            snapshot = build_content_workbench_snapshot(project_dir)

        self.assertEqual(snapshot["identity"]["botDisplayName"], "单小伊 Agent")
        self.assertEqual(snapshot["status"]["runId"], run_dir.name)
        self.assertEqual(snapshot["lastRequest"]["label"], "night_store")
        self.assertEqual(snapshot["history"][0]["status"], "completed")
        self.assertEqual(snapshot["selectedRunId"], run_dir.name)
        self.assertEqual(snapshot["selectedRunDetail"]["detailTitle"], "夜便利店")
        self.assertIn("service_state", snapshot["inventory"]["stateRoot"])
        self.assertIn("sidecars", snapshot["inventory"]["stateRoot"])

    def test_normalize_stale_status_marks_running_task_as_interrupted(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            write_workbench_status(
                project_dir,
                {
                    "status": "running",
                    "stage": "prompt builder layer",
                    "runId": "run-active",
                },
            )

            changed = normalize_stale_workbench_status(project_dir)
            snapshot = build_content_workbench_snapshot(project_dir)

        self.assertTrue(changed)
        self.assertEqual(snapshot["status"]["status"], "interrupted")
        self.assertIn("中断", snapshot["status"]["statusLabel"])

    def test_running_status_without_run_id_does_not_fall_back_to_previous_history_detail(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_dir = runs_root(project_dir) / "2026-04-11T20-00-00_content_workbench"
            (run_dir / "output").mkdir(parents=True, exist_ok=True)
            write_json(run_dir / "output" / "run_summary.json", {"runId": run_dir.name})
            append_run_index_record(
                project_dir,
                {
                    "status": "completed",
                    "runId": run_dir.name,
                    "runRoot": str(run_dir),
                    "summaryPath": str(run_dir / "output" / "run_summary.json"),
                    "request": {"sourceKind": "scene_draft_text", "endStage": "image", "label": "old_run"},
                },
            )
            write_workbench_status(
                project_dir,
                {
                    "status": "running",
                    "stage": "准备测试输入",
                    "runId": "",
                    "runRoot": "",
                    "request": {"sourceKind": "scene_draft_text", "endStage": "image", "label": "new_run"},
                },
            )

            snapshot = build_content_workbench_snapshot(project_dir)

        self.assertEqual(snapshot["status"]["status"], "running")
        self.assertEqual(snapshot["selectedRunId"], "__active__")
        self.assertIsNone(snapshot["selectedRunDetail"])
        self.assertEqual(snapshot["currentRunItem"]["selectionKey"], "__active__")

    def test_running_snapshot_keeps_old_selection_and_exposes_current_run_in_history(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            old_run_dir = runs_root(project_dir) / "2026-04-11T20-00-00_old"
            current_run_dir = runs_root(project_dir) / "2026-04-11T20-10-00_current"
            for run_dir in (old_run_dir, current_run_dir):
                (run_dir / "output").mkdir(parents=True, exist_ok=True)
                write_json(run_dir / "output" / "run_summary.json", {"runId": run_dir.name})
            append_run_index_record(
                project_dir,
                {
                    "status": "completed",
                    "runId": old_run_dir.name,
                    "runRoot": str(old_run_dir),
                    "summaryPath": str(old_run_dir / "output" / "run_summary.json"),
                    "request": {"sourceKind": "scene_draft_text", "endStage": "prompt", "label": "old_run"},
                },
            )
            write_workbench_status(
                project_dir,
                {
                    "status": "running",
                    "stage": "prompt builder layer",
                    "runId": current_run_dir.name,
                    "runRoot": str(current_run_dir),
                    "request": {"sourceKind": "scene_draft_text", "endStage": "image", "label": "current_run"},
                },
            )
            write_active_worker(project_dir, {"pid": 12345, "startedAt": "2026-04-11T20:10:00"})
            with patch("studio.content_workbench_store.is_process_alive", return_value=True):
                snapshot = build_content_workbench_snapshot(project_dir, selected_run_id=old_run_dir.name)

        self.assertEqual(snapshot["selectedRunId"], old_run_dir.name)
        self.assertEqual(snapshot["status"]["workerAlive"], True)
        self.assertEqual(snapshot["currentRunItem"]["selectionKey"], current_run_dir.name)
        self.assertEqual(snapshot["history"][0]["selectionKey"], old_run_dir.name)

    def test_reconcile_keeps_running_status_when_worker_is_alive(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            write_workbench_status(
                project_dir,
                {
                    "status": "running",
                    "stage": "execution layer",
                    "runId": "run-active",
                    "request": {"sourceKind": "scene_draft_text", "endStage": "image", "label": "active"},
                },
            )
            write_active_worker(project_dir, {"pid": 43210, "startedAt": "2026-04-11T20:20:00"})
            with patch("studio.content_workbench_store.is_process_alive", return_value=True):
                changed = reconcile_workbench_runtime_state(project_dir)
                snapshot = build_content_workbench_snapshot(project_dir)

        self.assertFalse(changed)
        self.assertEqual(snapshot["status"]["status"], "running")
        self.assertEqual(snapshot["currentRunItem"]["selectionKey"], "run-active")
        self.assertEqual(snapshot["history"], [])

    def test_reconcile_recovers_from_terminal_status_when_worker_is_alive(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            write_workbench_status(
                project_dir,
                {
                    "status": "completed",
                    "stage": "测试完成",
                    "runId": "run-active",
                    "request": {
                        "sourceKind": "scene_draft_text",
                        "endStage": "image",
                        "label": "active",
                        "sceneDraftText": "long body should not matter",
                    },
                },
            )
            write_active_worker(
                project_dir,
                {
                    "pid": 43210,
                    "startedAt": "2026-04-11T20:20:00",
                    "request": {
                        "sourceKind": "scene_draft_text",
                        "endStage": "image",
                        "label": "active",
                    },
                },
            )
            with patch("studio.content_workbench_store.is_process_alive", return_value=True):
                changed = reconcile_workbench_runtime_state(project_dir)
                snapshot = build_content_workbench_snapshot(project_dir)

        self.assertTrue(changed)
        self.assertEqual(snapshot["status"]["status"], "running")
        self.assertEqual(snapshot["status"]["stage"], "测试运行中")
        self.assertEqual(snapshot["currentRunItem"]["selectionKey"], "run-active")

    def test_snapshot_status_request_is_summarized(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            write_workbench_status(
                project_dir,
                {
                    "status": "running",
                    "stage": "准备测试输入",
                    "request": {
                        "sourceKind": "scene_draft_text",
                        "endStage": "image",
                        "label": "active",
                        "requestId": "req-1",
                        "sceneDraftText": "very long body",
                    },
                },
            )

            snapshot = build_content_workbench_snapshot(project_dir)

        self.assertEqual(
            snapshot["status"]["request"],
            {
                "sourceKind": "scene_draft_text",
                "endStage": "image",
                "label": "active",
                "requestId": "req-1",
            },
        )

    def test_run_index_and_cleanup_report_are_written_to_shared_state_root(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_dir = runs_root(project_dir) / "2026-04-11T20-00-00_content_workbench"
            output_dir = run_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            image_path = output_dir / "demo.png"
            image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            write_json(
                output_dir / "run_summary.json",
                {
                    "runId": run_dir.name,
                    "sceneDraftPremiseZh": "夜便利店",
                    "socialPostText": "窗边有雨，光影很安静。",
                    "positivePromptText": "balanced pose",
                    "generatedImagePath": str(image_path),
                    "promptPackagePath": str(run_dir / "prompt_guard" / "02_prompt_package.json"),
                    "creativePackagePath": str(run_dir / "creative" / "05_creative_package.json"),
                },
            )
            append_run_index_record(
                project_dir,
                {
                    "status": "completed",
                    "runId": run_dir.name,
                    "runRoot": str(run_dir),
                    "finishedAt": "2026-04-01T12:00:00",
                    "summaryPath": str(output_dir / "run_summary.json"),
                    "request": {
                        "label": "night_store",
                        "sourceKind": "scene_draft_text",
                        "endStage": "image",
                    },
                },
            )

            inventory = workbench_inventory_paths(project_dir)
            report = generate_cleanup_report(project_dir, older_than_days=0)
            self.assertIn("service_state", inventory["stateRoot"])
            self.assertIn("sidecars", inventory["stateRoot"])
            self.assertIn("generation_slot.json", inventory["generationSlotPath"])
            self.assertTrue(Path(inventory["runIndexJsonlPath"]).is_file())
            self.assertTrue(Path(inventory["runIndexCsvPath"]).is_file())
            self.assertTrue(Path(inventory["cleanupReportJsonPath"]).is_file())
            self.assertTrue(Path(inventory["cleanupReportCsvPath"]).is_file())
            self.assertEqual(report["candidateCount"], 1)

    def test_history_prefers_active_items_and_keeps_deleted_at_bottom(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            active_run = runs_root(project_dir) / "2026-04-11T20-10-00_active"
            deleted_run = runs_root(project_dir) / "2026-04-11T20-00-00_deleted"
            for run_dir in (active_run, deleted_run):
                (run_dir / "output").mkdir(parents=True, exist_ok=True)
                write_json(run_dir / "output" / "run_summary.json", {"runId": run_dir.name})
            append_run_index_record(
                project_dir,
                {
                    "status": "completed",
                    "runId": deleted_run.name,
                    "runRoot": str(deleted_run),
                    "finishedAt": "2026-04-11T20:00:00",
                    "summaryPath": str(deleted_run / "output" / "run_summary.json"),
                    "request": {"label": "old", "sourceKind": "scene_draft_text", "endStage": "image"},
                },
            )
            append_run_index_record(
                project_dir,
                {
                    "status": "completed",
                    "runId": active_run.name,
                    "runRoot": str(active_run),
                    "finishedAt": "2026-04-11T20:10:00",
                    "summaryPath": str(active_run / "output" / "run_summary.json"),
                    "request": {"label": "new", "sourceKind": "scene_draft_text", "endStage": "image"},
                },
            )
            records_path = project_dir / "runtime" / "service_state" / "sidecars" / "content_workbench" / "run_index.jsonl"
            records = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            records[0]["deleted"] = True
            records[0]["deletedAt"] = "2026-04-11T20:20:00"
            records_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records), encoding="utf-8")

            snapshot = build_content_workbench_snapshot(project_dir, history_limit=10)

        self.assertEqual(snapshot["history"][0]["runId"], active_run.name)
        self.assertTrue(snapshot["history"][-1]["deleted"])

    def test_reconcile_recovers_completed_status_when_worker_is_alive(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            write_workbench_status(
                project_dir,
                {
                    "status": "completed",
                    "stage": "测试完成",
                    "runId": "run-finished",
                    "request": {"sourceKind": "scene_draft_text", "endStage": "image", "label": "finished"},
                },
            )
            write_active_worker(project_dir, {"pid": 43210, "startedAt": "2026-04-11T20:20:00"})
            with patch("studio.content_workbench_store.is_process_alive", return_value=True):
                changed = reconcile_workbench_runtime_state(project_dir)
                snapshot = build_content_workbench_snapshot(project_dir)

        self.assertTrue(changed)
        self.assertEqual(snapshot["status"]["status"], "running")
        self.assertEqual(snapshot["status"]["stage"], "测试运行中")

    def test_migrate_legacy_content_workbench_state_removes_legacy_root(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            legacy_root = project_dir / "runtime" / "service_state" / "studio" / "content_workbench"
            legacy_root.mkdir(parents=True, exist_ok=True)
            (legacy_root / "latest_status.json").write_text('{"status":"completed"}', encoding="utf-8")

            migrated = migrate_legacy_content_workbench_state(project_dir)
            current_root = Path(workbench_inventory_paths(project_dir)["stateRoot"])
            self.assertTrue(migrated)
            self.assertTrue((current_root / "latest_status.json").exists())
            self.assertFalse(legacy_root.exists())


if __name__ == "__main__":
    unittest.main()
