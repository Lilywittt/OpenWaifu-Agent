from __future__ import annotations

import json
import shutil
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
    delete_workbench_run,
    generate_cleanup_report,
    migrate_legacy_content_workbench_state,
    normalize_stale_workbench_status,
    reconcile_workbench_runtime_state,
    toggle_workbench_favorite,
    write_active_worker,
    workbench_inventory_paths,
    write_last_request,
    write_workbench_status,
)


class ContentWorkbenchStoreTests(unittest.TestCase):
    def test_build_snapshot_orders_source_kinds_with_live_sampling_first(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)

            snapshot = build_content_workbench_snapshot(project_dir)

            source_kinds = snapshot["config"]["sourceKinds"]
        self.assertGreaterEqual(len(source_kinds), 2)
        self.assertEqual(source_kinds[0]["id"], "live_sampling")
        self.assertEqual(source_kinds[0]["label"], "实时采样全链路")
        self.assertEqual(source_kinds[1]["id"], "scene_draft_text")
        self.assertEqual(source_kinds[1]["label"], "场景稿文本或 JSON")

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
        self.assertIn("shared", snapshot["inventory"]["stateRoot"])
        self.assertIn("workbench", snapshot["inventory"]["stateRoot"])

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

    def test_stopping_snapshot_keeps_stop_available_while_worker_is_alive(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            write_workbench_status(
                project_dir,
                {
                    "status": "stopping",
                    "stage": "creative layer",
                    "runId": "run-stopping",
                    "request": {"sourceKind": "live_sampling", "endStage": "image", "label": "active"},
                },
            )
            write_active_worker(project_dir, {"pid": 43210, "startedAt": "2026-04-11T20:20:00"})
            with patch("studio.content_workbench_store.is_process_alive", return_value=True):
                snapshot = build_content_workbench_snapshot(project_dir)

        self.assertEqual(snapshot["status"]["status"], "stopping")
        self.assertTrue(snapshot["status"]["canStop"])

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
            self.assertIn("shared", inventory["stateRoot"])
            self.assertIn("workbench", inventory["stateRoot"])
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
            records_path = Path(workbench_inventory_paths(project_dir)["runIndexJsonlPath"])
            records = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            records[0]["deleted"] = True
            records[0]["deletedAt"] = "2026-04-11T20:20:00"
            records_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records), encoding="utf-8")

            snapshot = build_content_workbench_snapshot(project_dir, history_filter="all", history_limit=10)

        self.assertEqual(snapshot["history"][0]["runId"], active_run.name)
        self.assertTrue(snapshot["history"][-1]["deleted"])

    def test_snapshot_history_supports_filter_and_limit(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_ids = [
                "2026-04-11T20-00-00_one",
                "2026-04-11T20-10-00_two",
                "2026-04-11T20-20-00_three",
            ]
            for run_id in run_ids:
                run_dir = runs_root(project_dir) / run_id
                (run_dir / "output").mkdir(parents=True, exist_ok=True)
                write_json(run_dir / "output" / "run_summary.json", {"runId": run_id})
                append_run_index_record(
                    project_dir,
                    {
                        "status": "completed",
                        "runId": run_id,
                        "runRoot": str(run_dir),
                        "finishedAt": run_id.replace("_", ":", 1),
                        "summaryPath": str(run_dir / "output" / "run_summary.json"),
                        "request": {"label": run_id, "sourceKind": "scene_draft_text", "endStage": "image"},
                    },
                )

            records_path = Path(workbench_inventory_paths(project_dir)["runIndexJsonlPath"])
            records = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            records[0]["deleted"] = True
            records[0]["deletedAt"] = "2026-04-11T21:00:00"
            records_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records), encoding="utf-8")

            active_snapshot = build_content_workbench_snapshot(project_dir, history_filter="active", history_limit=1)
            deleted_snapshot = build_content_workbench_snapshot(project_dir, history_filter="deleted", history_limit=10)

        self.assertEqual(len(active_snapshot["history"]), 1)
        self.assertFalse(active_snapshot["history"][0]["deleted"])
        self.assertTrue(active_snapshot["historyPage"]["hasMore"])
        self.assertEqual(active_snapshot["historyPage"]["totalFiltered"], 2)
        self.assertEqual(deleted_snapshot["historyPage"]["filter"], "deleted")
        self.assertEqual(len(deleted_snapshot["history"]), 1)
        self.assertTrue(deleted_snapshot["history"][0]["deleted"])

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

    def test_snapshot_supports_favorites_filter_for_run(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_dir = runs_root(project_dir) / "2026-04-11T20-00-00_favorite_run"
            output_dir = run_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            write_json(
                output_dir / "run_summary.json",
                {
                    "runId": run_dir.name,
                    "sceneDraftPremiseZh": "收藏测试",
                },
            )
            append_run_index_record(
                project_dir,
                {
                    "status": "completed",
                    "runId": run_dir.name,
                    "runRoot": str(run_dir),
                    "summaryPath": str(output_dir / "run_summary.json"),
                    "request": {"label": "fav", "sourceKind": "scene_draft_text", "endStage": "image"},
                },
            )

            result = toggle_workbench_favorite(
                project_dir,
                {
                    "kind": "run",
                    "runId": run_dir.name,
                    "runRoot": str(run_dir),
                    "label": "fav",
                    "sourceKind": "scene_draft_text",
                    "endStage": "image",
                    "sceneDraftPremiseZh": "收藏测试",
                },
            )
            snapshot = build_content_workbench_snapshot(project_dir, history_filter="favorites")

        self.assertTrue(result["favorited"])
        self.assertEqual(snapshot["historyPage"]["filter"], "favorites")
        self.assertEqual(snapshot["historyStats"]["favorites"], 1)
        self.assertEqual(len(snapshot["history"]), 1)
        self.assertTrue(snapshot["history"][0]["favorite"])
        self.assertEqual(snapshot["history"][0]["runId"], run_dir.name)
        self.assertEqual(snapshot["selectedRunId"], run_dir.name)

    def test_snapshot_supports_favorites_filter_for_review_path(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_dir = runs_root(project_dir) / "2026-04-11T20-00-00_favorite_path"
            creative_dir = run_dir / "creative"
            output_dir = run_dir / "output"
            creative_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)
            write_json(
                creative_dir / "01_world_design.json",
                {"scenePremiseZh": "路径收藏", "worldSceneZh": "收藏 creative 目录"},
            )
            write_json(output_dir / "run_summary.json", {"runId": run_dir.name, "sceneDraftPremiseZh": "路径收藏"})

            toggle_workbench_favorite(
                project_dir,
                {
                    "kind": "path",
                    "path": str(creative_dir),
                    "label": "creative_dir",
                },
            )
            snapshot = build_content_workbench_snapshot(project_dir, history_filter="favorites")

        self.assertEqual(len(snapshot["history"]), 1)
        self.assertTrue(snapshot["history"][0]["favorite"])
        self.assertEqual(snapshot["history"][0]["favoriteKind"], "path")
        self.assertTrue(snapshot["selectedRunId"].startswith("path:"))
        self.assertEqual(snapshot["selectedRunDetail"]["runId"], run_dir.name)

    def test_delete_and_cleanup_skip_favorited_runs(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_dir = runs_root(project_dir) / "2026-04-11T20-00-00_protected"
            output_dir = run_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            write_json(output_dir / "run_summary.json", {"runId": run_dir.name, "sceneDraftPremiseZh": "保护目录"})
            append_run_index_record(
                project_dir,
                {
                    "status": "completed",
                    "runId": run_dir.name,
                    "runRoot": str(run_dir),
                    "finishedAt": "2026-04-01T12:00:00",
                    "summaryPath": str(output_dir / "run_summary.json"),
                    "request": {"label": "protected", "sourceKind": "scene_draft_text", "endStage": "image"},
                },
            )
            toggle_workbench_favorite(
                project_dir,
                {
                    "kind": "run",
                    "runId": run_dir.name,
                    "runRoot": str(run_dir),
                    "label": "protected",
                    "sourceKind": "scene_draft_text",
                    "endStage": "image",
                    "sceneDraftPremiseZh": "保护目录",
                },
            )

            with self.assertRaises(RuntimeError):
                delete_workbench_run(project_dir, run_dir.name)
            report = generate_cleanup_report(project_dir, older_than_days=0)

        self.assertEqual(report["candidateCount"], 0)

    def test_favorite_run_stays_visible_when_directory_was_removed_externally(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_dir = runs_root(project_dir) / "2026-04-11T20-00-00_missing_run"
            output_dir = run_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            write_json(output_dir / "run_summary.json", {"runId": run_dir.name, "sceneDraftPremiseZh": "外部删除"})
            append_run_index_record(
                project_dir,
                {
                    "status": "completed",
                    "runId": run_dir.name,
                    "runRoot": str(run_dir),
                    "summaryPath": str(output_dir / "run_summary.json"),
                    "request": {"label": "missing", "sourceKind": "scene_draft_text", "endStage": "image"},
                },
            )
            toggle_workbench_favorite(
                project_dir,
                {
                    "kind": "run",
                    "runId": run_dir.name,
                    "runRoot": str(run_dir),
                    "label": "missing",
                    "sceneDraftPremiseZh": "外部删除",
                },
            )
            shutil.rmtree(run_dir)

            snapshot = build_content_workbench_snapshot(project_dir, history_filter="favorites")

        self.assertEqual(len(snapshot["history"]), 1)
        self.assertEqual(snapshot["history"][0]["status"], "missing")
        self.assertEqual(snapshot["history"][0]["statusLabel"], "路径失效")
        self.assertEqual(snapshot["history"][0]["error"], "收藏的 run 目录当前不可用。")


if __name__ == "__main__":
    unittest.main()
