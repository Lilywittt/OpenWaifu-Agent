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
    build_existing_task_text,
    build_scene_draft_busy_text,
    build_developer_pending_text,
    build_failed_text,
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
        self.assertIn("模式会立即切换，但当前任务会继续跑完，不会被打断", text)

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

    def test_status_text_can_render_running_plus_user_pending_position(self):
        text = build_status_text_from_payload(
            {
                "status": "running",
                "stage": "execution layer: image prompt -> ComfyUI workflow -> generated image",
                "runId": "run-123",
                "queuePosition": 1,
                "queueSize": 1,
            }
        )
        self.assertIn("run-123", text)
        self.assertIn("你还有一条待处理请求", text)

    def test_status_text_can_render_busy_other(self):
        text = build_status_text_from_payload(
            {
                "status": "busy_other",
                "queuedCount": 2,
            }
        )
        self.assertIn("系统当前正在处理其他用户的任务", text)

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
        self.assertIn("如果你自己已经有任务在处理中，新的任务不会重复入队", text)

    def test_scene_draft_busy_text_explains_retry_after_finish(self):
        text = build_scene_draft_busy_text("当前正在执行生图")
        self.assertIn("你刚发来的这条消息不会并发启动新任务", text)
        self.assertIn("但如果你自己已经有任务在处理中，这条场景稿不会再次入队", text)

    def test_developer_input_received_text_can_explain_queued_scene_draft(self):
        from publish.qq_bot_private_ui import build_developer_input_received_text

        text = build_developer_input_received_text("午后的旧书店", queued=True)
        self.assertIn("已进入下一轮待处理", text)
        self.assertIn("不会影响当前正在生成的这一轮", text)
        self.assertIn("完成前，同一用户的新任务不会再次入队", text)

    def test_existing_task_text_explains_single_flight_rule(self):
        text = build_existing_task_text("当前正在生图中，处于体验者模式。阶段：正在执行生图", mode="experience")
        self.assertIn("你已经有一轮任务在处理中，本次不会重复加入队列", text)
        self.assertIn("当前正在生图中", text)
        self.assertIn("当前这轮完成、失败返回或被中断后", text)

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

    def test_failed_text_can_render_clear_social_sampling_error(self):
        class FakeSamplingError(RuntimeError):
            user_summary = "实时社媒采样失败，当前没有拿到新的外部样本。"
            user_details = [
                "失败位置：社媒采样，不是生图执行。",
                "建议：检查网络、代理或 VPN 后重试。",
            ]

        text = build_failed_text(FakeSamplingError("ignored"))
        self.assertIn("原因：实时社媒采样失败", text)
        self.assertIn("失败位置：社媒采样，不是生图执行。", text)
        self.assertIn("建议：检查网络、代理或 VPN 后重试。", text)


if __name__ == "__main__":
    unittest.main()
