from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from publish.qq_bot_job_queue import QQBotJobQueue
from publish.qq_bot_generate_service import (
    QQGenerateServiceAlreadyRunningError,
    _acquire_service_lock,
    _accept_full_generation,
    _accept_scene_draft_generation,
    _build_dynamic_publish_target,
    _build_dynamic_reply_target,
    _build_help_text,
    _load_latest_known_user_openid,
    _send_startup_guidance_if_possible,
    _build_started_text,
    _build_status_text,
    _interpret_private_message,
    _is_process_alive,
    _recv_gateway_payload,
    _release_service_lock,
    _should_reply_busy_once,
    cleanup_stale_service_lock,
    clear_service_stop_request,
    is_service_running,
    qq_bot_generate_service_state_root,
    read_service_lock,
    read_service_pid,
    read_service_status,
    read_service_stop_request,
    request_service_stop,
)


class QQBotGenerateServiceTests(unittest.TestCase):
    def _legacy_interpret_private_message_routes_real_world_inputs(self):
        cases = [
            {
                "name": "experience trigger",
                "content": "生成",
                "mode": "experience",
                "pending": "",
                "kind": "trigger_generation",
                "replyContains": "已开始生成",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "short alias trigger works",
                "content": "/g",
                "mode": "experience",
                "pending": "",
                "kind": "trigger_generation",
                "replyContains": "已开始生成",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "experience trigger with surrounding whitespace",
                "content": "  生成  ",
                "mode": "experience",
                "pending": "",
                "kind": "trigger_generation",
                "replyContains": "已开始生成",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "full width spaces still trigger generation",
                "content": "　生成　",
                "mode": "experience",
                "pending": "",
                "kind": "trigger_generation",
                "replyContains": "已开始生成",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "double quoted trigger is accepted",
                "content": '"生成"',
                "mode": "experience",
                "pending": "",
                "kind": "trigger_generation",
                "replyContains": "已开始生成",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "chinese quoted trigger is accepted",
                "content": "“生成”",
                "mode": "experience",
                "pending": "",
                "kind": "trigger_generation",
                "replyContains": "已开始生成",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "trigger with punctuation is accepted",
                "content": "生成。",
                "mode": "experience",
                "pending": "",
                "kind": "trigger_generation",
                "replyContains": "已开始生成",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "trigger with emoji is still unknown",
                "content": "生成🙂",
                "mode": "experience",
                "pending": "",
                "kind": "wrong_mode_command",
                "replyContains": "没有识别这条指令",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "numbered trigger is unknown",
                "content": "1. 生成",
                "mode": "experience",
                "pending": "",
                "kind": "wrong_mode_command",
                "replyContains": "没有识别这条指令",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "english help is unknown",
                "content": "help",
                "mode": "experience",
                "pending": "",
                "kind": "unknown",
                "replyContains": "没有识别这条指令",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "status with punctuation is accepted",
                "content": "状态！",
                "mode": "experience",
                "pending": "",
                "kind": "status",
                "replyContains": "当前空闲",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "short alias status works",
                "content": "/s",
                "mode": "experience",
                "pending": "",
                "kind": "status",
                "replyContains": "当前空闲",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "help with quotes is accepted",
                "content": "“帮助”",
                "mode": "experience",
                "pending": "",
                "kind": "help",
                "replyContains": "体验者模式",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "short alias help works",
                "content": "/h",
                "mode": "experience",
                "pending": "",
                "kind": "help",
                "replyContains": "体验者模式",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "blank input is unknown",
                "content": "   ",
                "mode": "experience",
                "pending": "",
                "kind": "unknown",
                "replyContains": "没有识别这条指令",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "help always works",
                "content": "帮助",
                "mode": "developer",
                "pending": "scene_draft_injection",
                "kind": "help",
                "replyContains": "开发者模式",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "status always works",
                "content": "状态",
                "mode": "developer",
                "pending": "scene_draft_injection",
                "kind": "status",
                "replyContains": "当前空闲",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "switch to developer mode",
                "content": "开发者模式",
                "mode": "experience",
                "pending": "",
                "kind": "switch_mode",
                "replyContains": "已切换到开发者模式",
                "nextMode": "developer",
                "nextPendingAction": "",
            },
            {
                "name": "short alias developer mode works",
                "content": "/d",
                "mode": "experience",
                "pending": "",
                "kind": "switch_mode",
                "replyContains": "已切换到开发者模式",
                "nextMode": "developer",
                "nextPendingAction": "",
            },
            {
                "name": "developer command with punctuation is accepted",
                "content": "开发者模式。",
                "mode": "experience",
                "pending": "",
                "kind": "switch_mode",
                "replyContains": "已切换到开发者模式",
                "nextMode": "developer",
                "nextPendingAction": "",
            },
            {
                "name": "switch back to experience clears pending action",
                "content": "体验者模式",
                "mode": "developer",
                "pending": "scene_draft_injection",
                "kind": "switch_mode",
                "replyContains": "已切换到体验者模式",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "short alias experience mode works",
                "content": "/e",
                "mode": "developer",
                "pending": "scene_draft_injection",
                "kind": "switch_mode",
                "replyContains": "已切换到体验者模式",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "developer prompt command sets pending action",
                "content": "注入场景稿",
                "mode": "experience",
                "pending": "",
                "kind": "unknown",
                "replyContains": "已进入场景稿注入态",
                "nextMode": "developer",
                "nextPendingAction": "scene_draft_injection",
            },
            {
                "name": "short alias developer prompt works",
                "content": "/i",
                "mode": "experience",
                "pending": "",
                "kind": "wrong_mode_command",
                "replyContains": "已进入场景稿注入态",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "blank while waiting scene draft keeps pending",
                "content": "   ",
                "mode": "developer",
                "pending": "scene_draft_injection",
                "kind": "awaiting_scene_draft",
                "replyContains": "当前正在等待场景设计内容",
                "nextMode": "developer",
                "nextPendingAction": "scene_draft_injection",
            },
            {
                "name": "plain text while waiting scene draft becomes scene submission",
                "content": "雨夜的书店门口，女孩抱着书站在屋檐下。",
                "mode": "developer",
                "pending": "scene_draft_injection",
                "kind": "scene_draft_submission",
                "replyContains": "已收到场景设计稿",
                "nextMode": "developer",
                "nextPendingAction": "scene_draft_injection",
                "scenePremiseZh": "",
            },
            {
                "name": "trigger command while waiting scene draft stays in developer mode",
                "content": "生成",
                "mode": "developer",
                "pending": "scene_draft_injection",
                "kind": "wrong_mode_command",
                "replyContains": "已开始按指定场景稿生成",
                "nextMode": "developer",
                "nextPendingAction": "scene_draft_injection",
            },
            {
                "name": "invalid scene draft json keeps pending",
                "content": '{"scenePremiseZh":"只有标题"}',
                "mode": "developer",
                "pending": "scene_draft_injection",
                "kind": "invalid_scene_draft",
                "replyContains": "场景设计稿格式不正确",
                "nextMode": "developer",
                "nextPendingAction": "scene_draft_injection",
            },
            {
                "name": "scene draft code fence is accepted",
                "content": '```json\n{"scenePremiseZh":"夜雨书店","worldSceneZh":"雨夜的书店门口，女孩抱着书站在屋檐下。"}\n```',
                "mode": "developer",
                "pending": "scene_draft_injection",
                "kind": "scene_draft_submission",
                "replyContains": "已收到场景设计稿",
                "nextMode": "developer",
                "nextPendingAction": "scene_draft_injection",
                "scenePremiseZh": "夜雨书店",
            },
            {
                "name": "scene draft json with outer whitespace is accepted",
                "content": '\n  {"scenePremiseZh":"阁楼午后","worldSceneZh":"午后的阁楼里，女孩翻开一本旧书。"}  \n',
                "mode": "developer",
                "pending": "scene_draft_injection",
                "kind": "scene_draft_submission",
                "replyContains": "已收到场景设计稿",
                "nextMode": "developer",
                "nextPendingAction": "scene_draft_injection",
                "scenePremiseZh": "阁楼午后",
            },
            {
                "name": "scene draft json without title is accepted",
                "content": '{"worldSceneZh":"午后的阁楼里，女孩翻开一本旧书。"}',
                "mode": "developer",
                "pending": "scene_draft_injection",
                "kind": "scene_draft_submission",
                "replyContains": "已收到场景设计稿",
                "nextMode": "developer",
                "nextPendingAction": "scene_draft_injection",
                "scenePremiseZh": "",
            },
            {
                "name": "raw json outside developer flow is unknown",
                "content": '{"scenePremiseZh":"夜雨书店","worldSceneZh":"雨夜的书店门口，女孩抱着书站在屋檐下。"}',
                "mode": "experience",
                "pending": "",
                "kind": "unknown",
                "replyContains": "没有识别这条指令",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "large arbitrary text stays unknown",
                "content": "随便输入一大段完全不符合指引的内容 " * 20,
                "mode": "experience",
                "pending": "",
                "kind": "unknown",
                "replyContains": "没有识别这条指令",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
        ]

        for case in cases:
            with self.subTest(case["name"]):
                result = _interpret_private_message(
                    content=case["content"],
                    user_mode=case["mode"],
                    pending_action=case["pending"],
                    status_text="当前空闲，处于体验者模式。",
                )
                self.assertEqual(result["kind"], case["kind"])
                self.assertIn(case["replyContains"], result["replyText"])
                self.assertEqual(result["nextMode"], case["nextMode"])
                self.assertEqual(result["nextPendingAction"], case["nextPendingAction"])
                if case["kind"] == "scene_draft_submission":
                    self.assertEqual(result["sceneDraft"]["scenePremiseZh"], case["scenePremiseZh"])

    def test_interpret_private_message_routes_real_world_inputs_mode_boundaries(self):
        cases = [
            {
                "name": "experience trigger",
                "content": "生成",
                "mode": "experience",
                "pending": "",
                "kind": "trigger_generation",
                "replyContains": "已开始生成",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "experience alias trigger",
                "content": "/g",
                "mode": "experience",
                "pending": "",
                "kind": "trigger_generation",
                "replyContains": "已开始生成",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "developer alias status",
                "content": "/s",
                "mode": "developer",
                "pending": "scene_draft_injection",
                "kind": "status",
                "replyContains": "开发者模式",
                "nextMode": "developer",
                "nextPendingAction": "scene_draft_injection",
            },
            {
                "name": "developer prompt works in developer mode",
                "content": "/i",
                "mode": "developer",
                "pending": "",
                "kind": "developer_scene_prompt",
                "replyContains": "已进入场景稿注入态",
                "nextMode": "developer",
                "nextPendingAction": "scene_draft_injection",
            },
            {
                "name": "developer prompt is blocked in experience mode",
                "content": "/i",
                "mode": "experience",
                "pending": "",
                "kind": "wrong_mode_command",
                "replyContains": "开发者模式",
                "nextMode": "experience",
                "nextPendingAction": "",
            },
            {
                "name": "experience trigger is blocked in developer mode",
                "content": "/g",
                "mode": "developer",
                "pending": "scene_draft_injection",
                "kind": "wrong_mode_command",
                "replyContains": "/e",
                "nextMode": "developer",
                "nextPendingAction": "scene_draft_injection",
            },
            {
                "name": "plain text while waiting scene draft becomes submission",
                "content": "雨夜的书店门口，女孩抱着书站在屋檐下。",
                "mode": "developer",
                "pending": "scene_draft_injection",
                "kind": "scene_draft_submission",
                "replyContains": "已收到场景设计稿",
                "nextMode": "developer",
                "nextPendingAction": "scene_draft_injection",
                "scenePremiseZh": "",
            },
        ]

        for case in cases:
            with self.subTest(case["name"]):
                status_text = (
                    "当前空闲，处于开发者模式。"
                    if case["mode"] == "developer"
                    else "当前空闲，处于体验者模式。"
                )
                result = _interpret_private_message(
                    content=case["content"],
                    user_mode=case["mode"],
                    pending_action=case["pending"],
                    status_text=status_text,
                )
                self.assertEqual(result["kind"], case["kind"])
                self.assertIn(case["replyContains"], result["replyText"])
                self.assertEqual(result["nextMode"], case["nextMode"])
                self.assertEqual(result["nextPendingAction"], case["nextPendingAction"])
                if case["kind"] == "scene_draft_submission":
                    self.assertEqual(result["sceneDraft"]["scenePremiseZh"], case["scenePremiseZh"])

    def test_same_mode_experience_command_returns_guidance_without_state_change(self):
        result = _interpret_private_message(
            content="体验者模式",
            user_mode="experience",
            pending_action="",
            status_text="当前空闲，处于体验者模式。",
        )

        self.assertEqual(result["kind"], "same_mode_guidance")
        self.assertEqual(result["nextMode"], "experience")
        self.assertEqual(result["nextPendingAction"], "")
        self.assertIn("体验者模式", result["replyText"])

    def test_same_mode_developer_command_preserves_scene_draft_pending_action(self):
        result = _interpret_private_message(
            content="开发者模式",
            user_mode="developer",
            pending_action="scene_draft_injection",
            status_text="当前空闲，处于开发者模式。",
        )

        self.assertEqual(result["kind"], "same_mode_guidance")
        self.assertEqual(result["nextMode"], "developer")
        self.assertEqual(result["nextPendingAction"], "scene_draft_injection")
        self.assertIn("已进入场景稿注入态", result["replyText"])

    def test_wrong_mode_command_accepts_punctuation_variant(self):
        result = _interpret_private_message(
            content="注入场景稿。",
            user_mode="experience",
            pending_action="",
            status_text="当前空闲，处于体验者模式。",
        )

        self.assertEqual(result["kind"], "wrong_mode_command")
        self.assertEqual(result["nextMode"], "experience")
        self.assertIn("开发者模式", result["replyText"])

    def test_interpret_private_message_unknown_developer_input_mentions_expected_commands(self):
        result = _interpret_private_message(
            content="随便说点什么",
            user_mode="developer",
            pending_action="",
            status_text="当前空闲，处于开发者模式。",
        )

        self.assertEqual(result["kind"], "unknown")
        self.assertIn("发送：注入场景稿", result["replyText"])
        self.assertIn("发送：体验者模式", result["replyText"])

    def test_interpret_private_message_pending_scene_draft_invalid_json_still_shows_json_guidance(self):
        result = _interpret_private_message(
            content='{"scenePremiseZh":"夜雨书店"',
            user_mode="developer",
            pending_action="scene_draft_injection",
            status_text="当前空闲，处于开发者模式。",
        )

        self.assertEqual(result["kind"], "invalid_scene_draft")
        self.assertIn("场景设计稿格式不正确", result["replyText"])
        self.assertIn("已进入场景稿注入态", result["replyText"])

    def test_is_process_alive_returns_false_for_invalid_pid(self):
        self.assertFalse(_is_process_alive(0))
        self.assertFalse(_is_process_alive(-1))

    def test_recv_gateway_payload_skips_empty_and_invalid_frames(self):
        class FakeWebSocket:
            def __init__(self):
                self._timeout = None
                self._messages = ["", "not-json", '{"op": 0, "t": "READY", "d": {}}']

            def gettimeout(self):
                return self._timeout

            def settimeout(self, value):
                self._timeout = value

            def recv(self):
                return self._messages.pop(0)

        raw_message, payload = _recv_gateway_payload(FakeWebSocket(), timeout_seconds=1.0)

        self.assertEqual(raw_message, '{"op": 0, "t": "READY", "d": {}}')
        self.assertEqual(payload["t"], "READY")

    def test_build_help_text_mentions_trigger_and_help_commands(self):
        text = _build_help_text("generate", "help")

        self.assertIn("generate", text)
        self.assertIn("help", text)

    def test_started_text_mentions_follow_up_delivery(self):
        text = _build_started_text()

        self.assertTrue(text)
        self.assertIn("完成", text)

    def test_status_text_reports_idle_when_no_active_task(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            state_root = qq_bot_generate_service_state_root(project_dir)
            (state_root / "latest_status.json").write_text(
                '{"status":"idle","stage":"completed","queuedCount":0}',
                encoding="utf-8",
            )

            text = _build_status_text(project_dir)

        self.assertIn("空闲", text)

    def test_status_text_can_render_developer_mode_label(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            state_root = qq_bot_generate_service_state_root(project_dir)
            (state_root / "latest_status.json").write_text(
                '{"status":"idle","stage":"completed","queuedCount":0}',
                encoding="utf-8",
            )

            text = _build_status_text(project_dir, mode="developer")

        self.assertIn("开发者模式", text)

    def test_status_text_prefers_user_queue_position_when_other_user_is_running(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            state_root = qq_bot_generate_service_state_root(project_dir)
            (state_root / "latest_status.json").write_text(
                '{"status":"running","stage":"execution layer","queuedCount":1,"userOpenId":"other-user","runId":"run-123"}',
                encoding="utf-8",
            )
            queue = QQBotJobQueue(project_dir)
            queue.enqueue(
                user_openid="user-1",
                job_kind="full_generation",
                payload={"taskType": "full_generation"},
                mode="experience",
            )

            text = _build_status_text(project_dir, user_openid="user-1", job_queue=queue)

        self.assertIn("队列位置：第 1 位", text)
        self.assertNotIn("run-123", text)

    def test_status_text_can_tell_idle_user_system_is_processing_other_users(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            state_root = qq_bot_generate_service_state_root(project_dir)
            (state_root / "latest_status.json").write_text(
                '{"status":"running","stage":"execution layer","queuedCount":2,"userOpenId":"other-user","runId":"run-123"}',
                encoding="utf-8",
            )
            queue = QQBotJobQueue(project_dir)

            text = _build_status_text(project_dir, user_openid="user-2", job_queue=queue)

        self.assertIn("系统当前正在处理其他用户的任务", text)

    def test_accept_full_generation_preserves_running_status_when_other_user_queues(self):
        import threading

        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            queue = QQBotJobQueue(project_dir)
            service_runtime = {
                "activeRunId": "run-active",
                "activeUserOpenId": "active-user",
                "activeSourceMessageId": "message-active",
                "currentStage": "execution layer: image prompt -> ComfyUI workflow -> generated image",
                "reserved": False,
            }
            lock = threading.Lock()

            result = _accept_full_generation(
                project_dir=project_dir,
                job_queue=queue,
                service_runtime=service_runtime,
                service_runtime_lock=lock,
                user_openid="queued-user",
                source_message_id="message-queued",
            )

            status_payload = read_service_status(project_dir)
            active_text = _build_status_text(project_dir, user_openid="active-user", job_queue=queue)
            queued_text = _build_status_text(project_dir, user_openid="queued-user", job_queue=queue)

        self.assertTrue(result["accepted"])
        self.assertEqual(status_payload["status"], "running")
        self.assertEqual(status_payload["userOpenId"], "active-user")
        self.assertEqual(status_payload["runId"], "run-active")
        self.assertEqual(status_payload["queuedCount"], 1)
        self.assertIn("run-active", active_text)
        self.assertIn("队列位置：第 1 位", queued_text)

    def test_accept_full_generation_blocks_same_user_when_running(self):
        import threading

        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            queue = QQBotJobQueue(project_dir)
            queue.enqueue(
                user_openid="user-1",
                job_kind="full_generation",
                payload={"taskType": "full_generation"},
                mode="experience",
            )
            queue.fetch_next_pending()
            service_runtime = {
                "activeRunId": "run-user-1",
                "activeUserOpenId": "user-1",
                "activeSourceMessageId": "message-active",
                "currentStage": "execution layer: image prompt -> ComfyUI workflow -> generated image",
                "reserved": False,
            }
            lock = threading.Lock()

            result = _accept_full_generation(
                project_dir=project_dir,
                job_queue=queue,
                service_runtime=service_runtime,
                service_runtime_lock=lock,
                user_openid="user-1",
                source_message_id="message-next",
            )

        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "user_inflight")
        self.assertEqual(result["inflightStatus"], "running")

    def test_accept_scene_draft_generation_blocks_same_user_when_pending(self):
        import threading

        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            queue = QQBotJobQueue(project_dir)
            queue.enqueue(
                user_openid="user-1",
                job_kind="scene_draft_to_image",
                payload={"taskType": "scene_draft_to_image"},
                mode="developer",
            )
            service_runtime = {
                "activeRunId": None,
                "activeUserOpenId": "",
                "activeSourceMessageId": "",
                "currentStage": "",
                "reserved": False,
            }
            lock = threading.Lock()

            result = _accept_scene_draft_generation(
                project_dir=project_dir,
                job_queue=queue,
                service_runtime=service_runtime,
                service_runtime_lock=lock,
                user_openid="user-1",
                scene_draft={"worldSceneZh": "雨夜的书店门口。", "scenePremiseZh": ""},
                scene_draft_path=project_dir / "scene.json",
                source_message_id="message-scene",
            )

        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "user_inflight")
        self.assertEqual(result["inflightStatus"], "pending")

    def test_build_dynamic_publish_target_uses_runtime_user_openid(self):
        target = _build_dynamic_publish_target("openid-demo")

        self.assertEqual(target["adapter"], "qq_bot_user")
        self.assertEqual(target["scene"], "user")
        self.assertEqual(target["targetOpenId"], "openid-demo")

    def test_build_dynamic_reply_target_adds_reply_context(self):
        target = _build_dynamic_reply_target(
            user_openid="openid-demo",
            source_message_id="message-demo",
            reply_message_seq=2,
            reply_event_id="event-demo",
        )

        self.assertEqual(target["replyMessageId"], "message-demo")
        self.assertEqual(target["replyMessageSeq"], 2)
        self.assertEqual(target["replyEventId"], "event-demo")

    def test_load_latest_known_user_openid_prefers_latest_gateway_state(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            state_path = (
                project_dir
                / "runtime"
                / "service_state"
                / "publish"
                / "qq_bot_gateway"
                / "latest_user_openid.json"
            )
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text('{"userOpenId":"openid-from-state"}', encoding="utf-8")
            (project_dir / ".env").write_text("QQ_BOT_USER_OPENID=openid-from-env\n", encoding="utf-8")

            resolved = _load_latest_known_user_openid(project_dir)

        self.assertEqual(resolved, "openid-from-state")

    def test_send_startup_guidance_if_possible_returns_false_when_no_user(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            result = _send_startup_guidance_if_possible(
                project_dir=project_dir,
                credentials={"appId": "appid", "appSecret": "secret", "apiBaseUrl": "https://api.sgroup.qq.com", "timeoutMs": 1000},
                trigger_command="生成",
                help_command="帮助",
                status_command="状态",
                log=None,
            )

        self.assertFalse(result)

    def test_send_startup_guidance_if_possible_sends_help_text_to_known_user(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            (project_dir / ".env").write_text("QQ_BOT_USER_OPENID=openid-demo\n", encoding="utf-8")
            captured = {}

            def fake_reply(**kwargs):
                captured.update(kwargs)
                return {"id": "msg-demo"}

            with patch("publish.qq_bot_generate_service._reply_text_for_user", side_effect=fake_reply):
                result = _send_startup_guidance_if_possible(
                    project_dir=project_dir,
                    credentials={"appId": "appid", "appSecret": "secret", "apiBaseUrl": "https://api.sgroup.qq.com", "timeoutMs": 1000},
                    trigger_command="生成",
                    help_command="帮助",
                    status_command="状态",
                    log=None,
                )

        self.assertTrue(result)
        self.assertEqual(captured["user_openid"], "openid-demo")
        self.assertIn("体验者模式", captured["text_content"])

    def test_state_root_is_under_publish_service_state(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            state_root = qq_bot_generate_service_state_root(project_dir)

            self.assertTrue(state_root.exists())
            self.assertIn("qq_bot_generate_service", str(state_root))

    def test_service_lock_can_be_acquired_and_released(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            lock_path = _acquire_service_lock(project_dir)

            self.assertTrue(lock_path.exists())
            _release_service_lock(lock_path)
            self.assertFalse(lock_path.exists())

    def test_service_lock_replaces_corrupt_pid_payload(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            state_root = qq_bot_generate_service_state_root(project_dir)
            lock_path = state_root / "service.lock.json"
            lock_path.write_text('{"pid":"bad-pid"}', encoding="utf-8")

            new_lock_path = _acquire_service_lock(project_dir)

            self.assertTrue(new_lock_path.exists())
            _release_service_lock(new_lock_path)

    def test_read_service_status_returns_none_when_missing(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)

            self.assertIsNone(read_service_status(project_dir))

    def test_service_lock_raises_friendly_error_when_other_pid_alive(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            state_root = qq_bot_generate_service_state_root(project_dir)
            lock_path = state_root / "service.lock.json"
            lock_path.write_text('{"pid": 12345}', encoding="utf-8")

            from unittest.mock import patch

            with patch("publish.qq_bot_generate_service._is_process_alive", return_value=True):
                with self.assertRaises(QQGenerateServiceAlreadyRunningError) as context:
                    _acquire_service_lock(project_dir)

        self.assertEqual(context.exception.pid, 12345)

    def test_request_and_clear_service_stop_request(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            request_service_stop(project_dir, reason="manual stop")
            payload = read_service_stop_request(project_dir)
            self.assertEqual(payload["reason"], "manual stop")
            clear_service_stop_request(project_dir)
            self.assertIsNone(read_service_stop_request(project_dir))

    def test_read_service_lock_returns_none_when_missing(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            self.assertIsNone(read_service_lock(project_dir))
            self.assertEqual(read_service_pid(project_dir), 0)
            self.assertFalse(is_service_running(project_dir))

    def test_cleanup_stale_service_lock_removes_dead_pid_lock(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            state_root = qq_bot_generate_service_state_root(project_dir)
            lock_path = state_root / "service.lock.json"
            lock_path.write_text('{"pid": 999999}', encoding="utf-8")

            removed = cleanup_stale_service_lock(project_dir)

            self.assertTrue(removed)
            self.assertFalse(lock_path.exists())

    def test_should_reply_busy_once_only_returns_true_first_time(self):
        import threading

        service_runtime = {"busyNoticeUsers": set()}
        lock = threading.Lock()

        self.assertTrue(_should_reply_busy_once(service_runtime, lock, user_openid="user-1"))
        self.assertFalse(_should_reply_busy_once(service_runtime, lock, user_openid="user-1"))
        self.assertTrue(_should_reply_busy_once(service_runtime, lock, user_openid="user-2"))


if __name__ == "__main__":
    unittest.main()
