from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from publish.qq_bot_private_ui import (
    MODE_DEVELOPER,
    build_busy_text,
    build_developer_continue_hint_text,
    build_scene_draft_busy_text,
    build_developer_pending_text,
    build_help_text,
    build_mode_switched_text,
    build_started_text,
    build_status_text_from_payload,
    build_unknown_command_text,
    build_wrong_mode_command_text,
)


class QQBotPrivateUITests(unittest.TestCase):
    def test_help_text_mentions_core_commands(self):
        text = build_help_text("生成", "帮助", "状态")
        self.assertIn("你现在可以直接发送（不带引号或序号）：", text)
        self.assertIn('1. "生成"', text)
        self.assertIn('2. "状态"', text)
        self.assertIn('3. "帮助"', text)
        self.assertIn('4. "开发者模式"', text)
        self.assertIn("/g /s /h /d", text)

    def test_developer_help_text_mentions_json_fields(self):
        text = build_help_text("生成", "帮助", "状态", mode=MODE_DEVELOPER)
        self.assertIn("worldSceneZh", text)
        self.assertIn("/i", text)
        self.assertIn("你可以直接发送场景设计正文，不必自己补完整 JSON", text)

    def test_mode_switched_text_for_developer_is_full_guide(self):
        text = build_mode_switched_text(MODE_DEVELOPER)
        self.assertIn('1. "注入场景稿"', text)
        self.assertIn('2. "/i"', text)
        self.assertIn("进入注入态后，后续非命令消息会直接按场景稿处理", text)
        self.assertIn('8. "/e"', text)

    def test_mode_switched_text_for_experience_is_full_guide(self):
        text = build_mode_switched_text("experience")
        self.assertIn('1. "生成"', text)
        self.assertIn('2. "/g"', text)
        self.assertIn('7. "开发者模式"', text)

    def test_mode_switched_text_can_explain_interrupting_running_task(self):
        text = build_mode_switched_text(MODE_DEVELOPER, task_running=True)
        self.assertIn("系统会先尝试中断当前任务", text)

    def test_status_text_renders_stage_and_run_id(self):
        text = build_status_text_from_payload(
            {
                "status": "running",
                "stage": "execution layer: image prompt -> ComfyUI workflow -> generated image",
                "runId": "run-123",
                "queuedCount": 0,
            }
        )
        self.assertIn("run-123", text)
        self.assertIn("当前正在生图中", text)
        self.assertIn("正在执行生图", text)

    def test_started_text_mentions_status_follow_up(self):
        text = build_started_text()
        self.assertIn("1 到 3 分钟", text)
        self.assertIn("状态", text)
        self.assertIn("完成后会直接回图片和社媒文案", text)

    def test_started_text_can_explain_interrupt_restart(self):
        text = build_started_text(interrupting=True)
        self.assertIn("已接收新的生成指令", text)
        self.assertIn("系统正在尝试中断当前这一轮任务", text)

    def test_busy_text_explains_wait_and_status(self):
        text = build_busy_text("当前正在执行生图")
        self.assertIn("当前正在生图，请稍等。", text)
        self.assertIn("当前正在执行生图", text)
        self.assertIn('1. "状态"', text)

    def test_developer_busy_text_mentions_mode_commands(self):
        text = build_busy_text("当前正在执行生图", mode=MODE_DEVELOPER)
        self.assertIn('5. "注入场景稿"', text)
        self.assertIn('7. "体验者模式"', text)
        self.assertIn("如果你发送命令，系统会按规则尝试中断当前任务", text)

    def test_scene_draft_busy_text_explains_retry_after_finish(self):
        text = build_scene_draft_busy_text("当前正在执行生图")
        self.assertIn("你刚发来的场景稿这次不会并发启动", text)
        self.assertIn("请等当前任务完成后，再重新发送这份场景稿", text)

    def test_developer_pending_text_explains_next_step(self):
        text = build_developer_pending_text()
        self.assertIn("当前正在等待场景设计内容", text)
        self.assertIn("体验者模式", text)

    def test_unknown_experience_text_mentions_no_quotes_or_numbers(self):
        text = build_unknown_command_text("生成", "帮助", "状态", mode="experience")
        self.assertIn("不要带引号、序号或句号", text)


    def test_wrong_mode_command_text_for_experience_points_to_developer_mode(self):
        text = build_wrong_mode_command_text(
            current_mode="experience",
            trigger_command="生成",
            help_command="帮助",
            status_command="状态",
        )
        self.assertIn("开发者模式", text)
        self.assertIn("/d", text)
        self.assertIn("/i", text)

    def test_wrong_mode_command_text_for_developer_points_to_exit_then_generate(self):
        text = build_wrong_mode_command_text(
            current_mode="developer",
            trigger_command="生成",
            help_command="帮助",
            status_command="状态",
        )
        self.assertIn("/e", text)
        self.assertIn("/g", text)

    def test_developer_continue_hint_mentions_staying_in_injection_mode(self):
        text = build_developer_continue_hint_text()
        self.assertIn("/e", text)
        self.assertIn("JSON", text)


if __name__ == "__main__":
    unittest.main()
