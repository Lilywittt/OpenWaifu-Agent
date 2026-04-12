from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from io_utils import write_json
from ops.dashboard_store import (
    build_dashboard_run_detail_snapshot,
    build_dashboard_snapshot,
    build_run_detail_snapshot,
    resolve_dashboard_generated_image_artifact,
    resolve_generated_image_artifact,
)
from publish.qq_bot_job_queue import QQBotJobQueue
from publish.qq_bot_runtime_store import qq_bot_generate_service_state_root, write_stage_status
from runtime_layout import runs_root, runtime_root


class OpsDashboardStoreTests(unittest.TestCase):
    def test_build_dashboard_snapshot_reads_service_queue_sampling_and_runs(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            (project_dir / ".env").write_text("QQ_BOT_DISPLAY_NAME=单小伊 Agent\n", encoding="utf-8")
            state_root = qq_bot_generate_service_state_root(project_dir)
            state_root.mkdir(parents=True, exist_ok=True)
            (state_root / "service.lock.json").write_text(
                '{"pid": 12345, "startedAt": "2026-04-11T12:00:00"}',
                encoding="utf-8",
            )
            write_stage_status(
                project_dir=project_dir,
                status="running",
                stage="execution layer: image prompt -> ComfyUI workflow -> generated image",
                user_openid="ABCDEF1234567890",
                run_id="2026-04-11T12-00-59_qqbot_generate_active",
                queued_count=1,
            )
            (state_root / "service_events.jsonl").write_text(
                '{"recordedAt":"2026-04-11T12:00:01","type":"generation_started","runId":"2026-04-11T12-00-59_qqbot_generate_active","userOpenId":"ABCDEF1234567890"}\n'
                '{"recordedAt":"2026-04-11T12:01:01","type":"generation_log","message":"execution layer"}\n',
                encoding="utf-8",
            )
            stdout_path = runtime_root(project_dir) / "service_logs" / "publish" / "qq_bot_generate_service.stdout.log"
            stderr_path = runtime_root(project_dir) / "service_logs" / "publish" / "qq_bot_generate_service.stderr.log"
            stdout_path.parent.mkdir(parents=True, exist_ok=True)
            stdout_path.write_text("stdout line 1\nstdout line 2\n", encoding="utf-8")
            stderr_path.write_text("stderr line 1\n", encoding="utf-8")

            queue = QQBotJobQueue(project_dir)
            queue.enqueue(
                user_openid="pending-user",
                job_kind="full_generation",
                payload={"taskType": "full_generation"},
                mode="experience",
            )
            queue.enqueue(
                user_openid="running-user",
                job_kind="scene_draft_to_image",
                payload={"taskType": "scene_draft_to_image"},
                mode="developer",
            )
            running = queue.fetch_next_pending()
            queue.mark_completed(int(running["jobId"]), run_id="run-finished")

            sampling_path = runtime_root(project_dir) / "service_state" / "social_sampling_health.json"
            write_json(
                sampling_path,
                {
                    "updatedAt": "2026-04-11T12:02:00",
                    "lastSample": {
                        "at": "2026-04-11T12:01:00",
                        "sourceZh": "Reddit",
                        "providerZh": "Reddit / food",
                        "sampledSignalsZh": ["今天的花园和猫看起来都很舒服。"],
                    },
                    "sourceBackoff": {
                        "reddit": {
                            "blockedUntil": "2026-04-11T18:00:00",
                            "lastError": "timeout",
                        }
                    },
                    "partitionBackoff": {},
                    "partitions": {
                        "reddit_food": {
                            "providerZh": "Reddit / food",
                            "sourceZh": "Reddit",
                            "consecutiveFailures": 2,
                            "failureCount": 3,
                            "lastError": "timeout",
                        }
                    },
                },
            )

            run_dir = runs_root(project_dir) / "2026-04-11T12-03-00_qqbot_generate_demo"
            (run_dir / "output").mkdir(parents=True)
            image_path = run_dir / "output" / "demo.png"
            image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            write_json(
                run_dir / "output" / "run_summary.json",
                {
                    "runId": run_dir.name,
                    "sceneDraftPremiseZh": "雨后花圃的意外访客",
                    "socialPostText": "今天天气比想象中好很多。",
                    "generatedImagePath": str(image_path),
                    "publishReceipts": [
                        {
                            "publishedAt": "2026-04-11T12:05:00",
                            "status": "published",
                            "targetOpenId": "ABCDEF1234567890",
                        }
                    ],
                },
            )
            ignored_run_dir = runs_root(project_dir) / "2026-04-11T12-04-00_workbench_01"
            (ignored_run_dir / "output").mkdir(parents=True)
            write_json(
                ignored_run_dir / "output" / "run_summary.json",
                {
                    "runId": ignored_run_dir.name,
                    "sceneDraftPremiseZh": "should be ignored",
                },
            )

            snapshot = build_dashboard_snapshot(project_dir)

        self.assertEqual(snapshot["service"]["status"], "running")
        self.assertEqual(snapshot["identity"]["botDisplayName"], "单小伊 Agent")
        self.assertEqual(snapshot["service"]["runId"], "2026-04-11T12-00-59_qqbot_generate_active")
        self.assertEqual(snapshot["queue"]["pendingCount"], 1)
        self.assertEqual(len(snapshot["queue"]["pendingJobs"]), 1)
        self.assertEqual(snapshot["sampling"]["lastSample"]["providerZh"], "Reddit / food")
        self.assertEqual(len(snapshot["recentRuns"]), 1)
        self.assertEqual(
            snapshot["recentRuns"][0]["imageRoute"],
            "/artifacts/generated-image?runId=2026-04-11T12-03-00_qqbot_generate_demo",
        )
        self.assertTrue(snapshot["logs"]["stdoutTail"])
        self.assertEqual(snapshot["events"][0]["type"], "generation_log")
        self.assertEqual(
            snapshot["service"]["runDetailRoute"],
            "/runs/detail?runId=2026-04-11T12-00-59_qqbot_generate_active",
        )
        self.assertEqual(
            snapshot["recentRuns"][0]["detailRoute"],
            "/runs/detail?runId=2026-04-11T12-03-00_qqbot_generate_demo",
        )

    def test_build_dashboard_snapshot_handles_missing_and_invalid_files(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            state_root = qq_bot_generate_service_state_root(project_dir)
            state_root.mkdir(parents=True, exist_ok=True)
            (state_root / "service_events.jsonl").write_text("not-json\n", encoding="utf-8")
            (state_root / "latest_status.json").write_text("not-json", encoding="utf-8")

            snapshot = build_dashboard_snapshot(project_dir, event_limit=5, run_limit=3)

        self.assertEqual(snapshot["service"]["status"], "unknown")
        self.assertFalse(snapshot["queue"]["dbExists"])
        self.assertEqual(snapshot["events"][0]["type"], "invalid_jsonl")
        self.assertEqual(snapshot["recentRuns"], [])

    def test_resolve_generated_image_artifact_rejects_escape_path(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_dir = runs_root(project_dir) / "2026-04-11T12-03-00_qqbot_generate_demo"
            (run_dir / "output").mkdir(parents=True)
            outside_path = project_dir / "outside.png"
            outside_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            write_json(
                run_dir / "output" / "run_summary.json",
                {
                    "generatedImagePath": str(outside_path),
                },
            )

            resolved = resolve_generated_image_artifact(project_dir, "2026-04-11T12-03-00_qqbot_generate_demo")

        self.assertIsNone(resolved)

    def test_build_run_detail_snapshot_reads_sampling_and_design_sections(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_dir = runs_root(project_dir) / "2026-04-11T18-30-00_qqbot_generate_demo"
            creative_dir = run_dir / "creative"
            output_dir = run_dir / "output"
            creative_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "prompt_guard").mkdir(parents=True, exist_ok=True)
            image_path = output_dir / "demo.png"
            image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            write_json(
                creative_dir / "01_world_design_input.json",
                {
                    "socialSignalSample": {
                        "sourceZh": "Bangumi",
                        "providerZh": "Bangumi / 动画分区",
                        "sampledSignalsZh": ["深夜便利店里的动画余韵"],
                    }
                },
            )
            write_json(
                creative_dir / "01_world_design.json",
                {
                    "scenePremiseZh": "深夜便利店",
                    "worldSceneZh": "她在深夜便利店靠窗坐下，开始画刚看完动画里的角色。",
                },
            )
            (creative_dir / "02_environment_design.md").write_text("环境设计正文", encoding="utf-8")
            (creative_dir / "03_styling_design.md").write_text("造型设计正文", encoding="utf-8")
            (creative_dir / "04_action_design.md").write_text("动作设计正文", encoding="utf-8")
            write_json(
                run_dir / "prompt_builder" / "01_prompt_package.json",
                {
                    "meta": {
                        "createdAt": "2026-04-11T18:31:00",
                        "runMode": "default",
                    },
                    "positivePrompt": "sunset light, old bookstore, solo girl",
                    "negativePrompt": "nsfw, adult face, bad hands",
                },
            )
            write_json(
                run_dir / "prompt_guard" / "01_review_report.json",
                {
                    "status": "revised",
                    "changed": True,
                    "issues": ["hand conflict"],
                    "changeSummary": "tightened hand action and body direction",
                },
            )
            write_json(
                run_dir / "prompt_guard" / "02_prompt_package.json",
                {
                    "meta": {
                        "createdAt": "2026-04-11T18:32:00",
                        "runMode": "default",
                    },
                    "positivePrompt": "sunset light, old bookstore, solo girl, balanced pose",
                    "negativePrompt": "nsfw, adult face, bad hands",
                    "reviewStatus": "revised",
                    "promptChanged": True,
                },
            )
            write_json(
                output_dir / "run_summary.json",
                {
                    "runId": run_dir.name,
                    "sceneDraftPremiseZh": "深夜便利店",
                    "socialPostText": "今天的深夜便利店很像一格被拉长的动画分镜。",
                    "generatedImagePath": str(image_path),
                    "publishReceipts": [
                        {
                            "status": "published",
                            "publishedAt": "2026-04-11T18:33:00",
                            "targetOpenId": "ABCDEF1234567890",
                        }
                    ],
                },
            )

            snapshot = build_run_detail_snapshot(project_dir, run_dir.name)

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot["detailTitle"], "深夜便利店")
        self.assertEqual(snapshot["sectionCounts"]["available"], 8)
        self.assertEqual(snapshot["sections"][0]["title"], "采样原始内容")
        self.assertEqual(snapshot["sections"][0]["metaRows"][0]["value"], "Bangumi")
        self.assertEqual(snapshot["sections"][1]["metaRows"][0]["value"], "深夜便利店")
        self.assertEqual(snapshot["sections"][5]["title"], "最终生图 Prompt")
        self.assertIn("正向 Prompt", snapshot["sections"][5]["bodyText"])
        self.assertEqual(snapshot["sections"][5]["metaRows"][0]["value"], "2026-04-11T18:32:00")
        self.assertEqual(snapshot["sections"][5]["metaRows"][2]["value"], "revised")
        self.assertEqual(snapshot["sections"][6]["title"], "Prompt 回调前后对比")
        self.assertEqual(snapshot["sections"][6]["bodyText"], "")
        self.assertEqual(len(snapshot["sections"][6]["compareBlocks"]), 4)
        self.assertEqual(snapshot["sections"][6]["compareBlocks"][0]["title"], "回调前 正向 Prompt")
        self.assertTrue(
            any(
                segment["changed"]
                for block in snapshot["sections"][6]["compareBlocks"]
                for segment in block["segments"]
            )
        )
        self.assertTrue(any("balanced pose" in segment["text"] for segment in snapshot["sections"][6]["compareBlocks"][1]["segments"]))
        self.assertEqual(snapshot["sections"][7]["title"], "Prompt 回调报告")
        self.assertEqual(snapshot["sections"][7]["metaRows"][0]["value"], "revised")
        self.assertEqual(snapshot["imageRoute"], f"/artifacts/generated-image?runId={run_dir.name}")
        self.assertEqual(snapshot["publishStatus"], "published")

    def test_dashboard_detail_helpers_reject_non_qq_runs(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_dir = runs_root(project_dir) / "2026-04-11T18-30-00_workbench_01"
            (run_dir / "output").mkdir(parents=True, exist_ok=True)
            image_path = run_dir / "output" / "demo.png"
            image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            write_json(
                run_dir / "output" / "run_summary.json",
                {"runId": run_dir.name, "generatedImagePath": str(image_path)},
            )

            snapshot = build_dashboard_run_detail_snapshot(project_dir, run_dir.name)
            image = resolve_dashboard_generated_image_artifact(project_dir, run_dir.name)

        self.assertIsNone(snapshot)
        self.assertIsNone(image)


if __name__ == "__main__":
    unittest.main()
