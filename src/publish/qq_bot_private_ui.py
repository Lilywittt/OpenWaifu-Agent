from __future__ import annotations

import json
from typing import Any


MODE_EXPERIENCE = "experience"
MODE_DEVELOPER = "developer"


def normalize_private_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized == MODE_DEVELOPER:
        return MODE_DEVELOPER
    return MODE_EXPERIENCE


def normalize_stage_label(stage: str) -> str:
    normalized = str(stage or "").strip()
    stage_map = {
        "initializing": "正在初始化服务",
        "waiting_for_trigger": "正在等待指令",
        "queued_for_generation": "任务已进入队列",
        "queued_for_scene_draft_generation": "场景稿任务已进入队列",
        "starting": "正在启动本轮生成",
        "gateway_reconnecting": "正在重连 QQ 网关",
        "completed": "已经完成",
        "interrupted": "已被命令中断",
        "creative layer: character assets + social sampling -> scene draft -> three design drafts": "正在生成场景稿和三份设计稿",
        "creative layer: existing scene draft -> three design drafts": "正在根据现成场景稿生成三份设计稿",
        "social post layer: character assets + scene draft -> social post text": "正在撰写社媒文案",
        "prompt builder layer: character assets + three design drafts -> image prompt": "正在整理生图提示词",
        "prompt guard layer: final prompt review -> minimal patch": "正在回调审核生图 Prompt",
        "execution layer: image prompt -> ComfyUI workflow -> generated image": "正在执行生图",
        "publish layer: image + social post -> publish targets": "正在把结果回传到 QQ",
    }
    return stage_map.get(normalized, normalized or "阶段未知")


def build_help_text(trigger_command: str, help_command: str, status_command: str, *, mode: str = MODE_EXPERIENCE) -> str:
    resolved_mode = normalize_private_mode(mode)
    if resolved_mode == MODE_DEVELOPER:
        return "\n".join(
            [
                "开发者模式",
                "",
                "你现在可以直接发送（不带引号或序号）：",
                '1. "注入场景稿"',
                '2. "/i"',
                f'3. "{status_command}"',
                '4. "/s"',
                f'5. "{help_command}"',
                '6. "/h"',
                '7. "体验者模式"',
                '8. "/e"',
                "",
                "使用方式：",
                "1. 先发送“注入场景稿”或“/i”进入注入态",
                "2. 进入注入态后，后续非命令消息都会按新的场景稿处理",
                "3. 你可以直接发送场景设计正文，不必自己补完整 JSON",
                "4. 如果发送 JSON，只要求 worldSceneZh，scenePremiseZh 可以为空",
                "5. 想退出开发者模式时，发送“体验者模式”或“/e”",
                "",
                "JSON 示例：",
                developer_scene_draft_template(),
            ]
        )
    return "\n".join(
        [
            "体验者模式",
            "",
            "你现在可以直接发送（不带引号或序号）：",
            f'1. "{trigger_command}"',
            f'2. "{status_command}"',
            f'3. "{help_command}"',
            '4. "开发者模式"',
            "",
            "也支持超短别名：/g /s /h /d",
            "",
            "说明：",
            "1. 单次生成通常需要 1 到 3 分钟",
            "2. 同一用户必须等当前任务完成后，才能再次提交新任务",
            "3. 完成后会直接回图片和社媒文案",
            "",
            "第一次使用时，直接发送“生成”就可以。",
        ]
    )


def build_started_text(*, mode: str = MODE_EXPERIENCE, interrupting: bool = False) -> str:
    resolved_mode = normalize_private_mode(mode)
    if resolved_mode == MODE_DEVELOPER:
        lines = [
            "已开始按指定场景稿生成" if not interrupting else "已接收新的生成指令",
            "",
            "模式：开发者模式",
            "预计耗时：1 到 3 分钟",
            "当前会继续保持在注入态。",
            "现在不用重复发送 JSON。",
            "需要看进度时，发送“状态”或“/s”。",
            "完成后会直接回图片和社媒文案。",
        ]
    else:
        lines = [
            "已开始生成" if not interrupting else "已接收新的生成指令",
            "",
            "模式：体验者模式",
            "预计耗时：1 到 3 分钟",
            "现在不用重复发送“生成”。",
            "需要看进度时，发送“状态”或“/s”。",
            "完成后会直接回图片和社媒文案。",
        ]
    if interrupting:
        lines.extend(
            [
                "",
                "说明：",
                "1. 系统正在尝试中断当前这一轮任务",
                "2. 中断完成后，会按你最新的命令重新开始",
            ]
        )
    return "\n".join(lines)


def build_busy_text(status_text: str = "", *, mode: str = MODE_EXPERIENCE) -> str:
    resolved_mode = normalize_private_mode(mode)
    lines = ["当前正在生图，请稍等。"]
    if status_text:
        lines.extend(["", status_text])
    if resolved_mode == MODE_DEVELOPER:
        lines.extend(
            [
                "",
                "你现在仍然可以直接发送（不带引号或序号）：",
                '1. "状态"',
                '2. "/s"',
                '3. "帮助"',
                '4. "/h"',
                '5. "注入场景稿"',
                '6. "/i"',
                '7. "体验者模式"',
                '8. "/e"',
                "",
                "说明：",
                "1. 这一条普通消息不会并发启动新任务",
                "2. 如果你发送命令，系统会按规则处理，但不会打断当前任务",
                "3. 如果你自己已经有任务在处理中，新的任务不会重复入队",
                "4. 如果只是想看进度，请发送“状态”或“/s”",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "你现在仍然可以直接发送（不带引号或序号）：",
                '1. "状态"',
                '2. "/s"',
                '3. "帮助"',
                '4. "/h"',
                '5. "开发者模式"',
                '6. "/d"',
                "",
                "说明：",
                "1. 这一条普通消息不会触发新的生成",
                "2. 同一用户在当前任务完成前，不能重复提交新的生成任务",
                "3. 如果只是想看进度，请发送“状态”或“/s”",
            ]
        )
    return "\n".join(lines)


def build_scene_draft_busy_text(status_text: str = "") -> str:
    lines = ["当前正在生图，请稍等。"]
    if status_text:
        lines.extend(["", status_text])
    lines.extend(
        [
            "",
            "你刚发来的这条消息不会并发启动新任务。",
            "如果你想提交下一轮场景稿，请直接发送一份格式正确的场景稿。",
            "但如果你自己已经有任务在处理中，这条场景稿不会再次入队。",
            "",
            "你现在仍然可以直接发送（不带引号或序号）：",
            '1. "状态"',
            '2. "/s"',
            '3. "帮助"',
            '4. "/h"',
            '5. "体验者模式"',
            '6. "/e"',
        ]
    )
    return "\n".join(lines)


def build_failed_text(exc: Exception) -> str:
    user_summary = str(getattr(exc, "user_summary", "")).strip()
    user_details = [str(item).strip() for item in getattr(exc, "user_details", []) if str(item).strip()]
    if user_summary:
        return "\n".join(
            [
                "这次生成没有完成",
                "",
                f"原因：{user_summary}",
                *user_details,
                "",
                "现场已经保留。",
                "你可以稍后重试，或者先发送“状态”查看最新状态。",
            ]
        )
    text = str(exc).strip() or exc.__class__.__name__
    return "\n".join(
        [
            "这次生成没有完成",
            "",
            f"错误摘要：{text[:120]}",
            "",
            "现场已经保留。",
            "你可以稍后重试，或者先发送“状态”查看最新状态。",
        ]
    )


def build_enqueued_text(queue_position: int, queue_size: int, *, mode: str = MODE_EXPERIENCE) -> str:
    resolved_mode = normalize_private_mode(mode)
    position = int(queue_position or 0)
    size = int(queue_size or 0)
    position_text = "队列位置未知"
    if position > 0:
        position_text = f"队列位置：第 {position} 位"
        if size > 0:
            position_text += f"（共 {size} 条）"
    lines = [
        "已加入队列",
        "",
        position_text,
        f"当前模式：{'开发者模式' if resolved_mode == MODE_DEVELOPER else '体验者模式'}",
        "",
        "你可以发送“状态”查看进度。",
    ]
    return "\n".join(lines)


def build_queue_full_text(queue_size: int) -> str:
    size = int(queue_size or 0)
    size_text = f"当前队列已满（共 {size} 条任务）。" if size else "当前队列已满。"
    return "\n".join(
        [
            size_text,
            "请稍后再试，或先发送“状态”查看进度。",
        ]
    )


def build_mode_switched_text(mode: str, *, task_running: bool = False) -> str:
    resolved_mode = normalize_private_mode(mode)
    if resolved_mode == MODE_DEVELOPER:
        lines = [
            "已切换到开发者模式",
            "",
            "你现在可以直接发送（不带引号或序号）：",
            '1. "注入场景稿"',
            '2. "/i"',
            '3. "状态"',
            '4. "/s"',
            '5. "帮助"',
            '6. "/h"',
            '7. "体验者模式"',
            '8. "/e"',
            "",
            "使用方式：",
            "1. 先发送“注入场景稿”或“/i”进入注入态",
            "2. 进入注入态后，后续非命令消息会直接按场景稿处理",
            "3. 你可以直接发送场景设计正文，也可以发送 JSON",
            "4. 如果发 JSON，只要求 worldSceneZh，scenePremiseZh 可以为空",
            "5. 想回到普通使用时，发送“体验者模式”或“/e”",
        ]
        if task_running:
            lines.extend(
                [
                    "",
                    "注意：",
                    "1. 当前已有一轮任务正在运行",
                    "2. 模式会立即切换，但当前任务会继续跑完，不会被打断",
                    "3. 如需看进度，请发送“状态”或“/s”",
                ]
            )
        return "\n".join(lines)
    lines = [
        "已切换到体验者模式",
        "",
        "你现在可以直接发送（不带引号或序号）：",
        '1. "生成"',
        '2. "/g"',
        '3. "状态"',
        '4. "/s"',
        '5. "帮助"',
        '6. "/h"',
        '7. "开发者模式"',
        '8. "/d"',
        "",
                "说明：",
                "1. 单次生成通常需要 1 到 3 分钟",
                "2. 同一用户必须等当前任务完成后，才能再次提交新任务",
                "3. 完成后会直接回图片和社媒文案",
        "4. 想进入开发者模式时，发送“开发者模式”或“/d”",
    ]
    if task_running:
        lines.extend(
            [
                "",
                    "注意：",
                    "1. 当前已有一轮任务正在运行",
                    "2. 模式会立即切换，但当前任务会继续跑完，不会被打断",
                    "3. 如需看进度，请发送“状态”或“/s”",
            ]
        )
    return "\n".join(lines)


def build_developer_input_text(*, task_running: bool = False) -> str:
    lines = [
        "已进入场景稿注入态",
        "",
        "当前状态：后续非命令消息都会按新的场景稿处理。",
        "下一步：直接发送场景设计正文，或发送 JSON。",
        "JSON 只要求 worldSceneZh，scenePremiseZh 可以为空。",
        "",
        "JSON 示例：",
        developer_scene_draft_template(),
        "",
        "退出方式：发送“体验者模式”或“/e”。",
    ]
    if task_running:
        lines.extend(
            [
                "",
                "注意：",
                "1. 当前已有一轮任务正在运行",
                "2. 当前任务会继续跑完，完成前不会再接收你新的场景稿任务",
                "3. 如需看进度，请发送“状态”或“/s”",
            ]
        )
    return "\n".join(lines)


def build_developer_pending_text() -> str:
    return "\n".join(
        [
            "当前正在等待场景设计内容",
            "",
            "下一步：直接发送正文，或发送 JSON。",
            "如果想退出开发者模式，发送“体验者模式”或“/e”。",
        ]
    )


def build_developer_input_received_text(scene_premise: str, *, queued: bool = False) -> str:
    summary = str(scene_premise or "").strip() or "未提供场景命题"
    if queued:
        return "\n".join(
            [
                "已收到场景设计稿",
                "",
                f"场景命题：{summary}",
                "当前状态：这份场景稿已进入下一轮待处理，不会影响当前正在生成的这一轮。",
                "下一步：请等待这轮任务完成。完成前，同一用户的新任务不会再次入队。",
                "查看进度：发送“状态”或“/s”。",
            ]
        )
    return "\n".join(
        [
            "已收到场景设计稿",
            "",
            f"场景命题：{summary}",
            "当前状态：这份场景稿已进入处理流程。",
            "下一步：等待结果。完成前，同一用户的新任务不会再次入队。",
            "查看进度：发送“状态”或“/s”。",
        ]
    )


def build_existing_task_text(status_text: str = "", *, mode: str = MODE_EXPERIENCE) -> str:
    resolved_mode = normalize_private_mode(mode)
    lines = ["你已经有一轮任务在处理中，本次不会重复加入队列。"]
    if status_text:
        lines.extend(["", status_text])
    if resolved_mode == MODE_DEVELOPER:
        lines.extend(
            [
                "",
                "说明：",
                "1. 请等待当前这轮完成、失败返回或被中断后，再提交新的场景稿任务",
                "2. 如果你只是想看进度，请发送“状态”或“/s”",
                "3. 如果你想退出开发者模式，请发送“体验者模式”或“/e”",
            ]
        )
        return "\n".join(lines)
    lines.extend(
        [
            "",
            "说明：",
            "1. 请等待当前这轮完成、失败返回或被中断后，再发起新的生成任务",
            "2. 如果你只是想看进度，请发送“状态”或“/s”",
            "3. 如果你想查看可用指令，请发送“帮助”或“/h”",
        ]
    )
    return "\n".join(lines)


def build_external_slot_busy_text(slot_text: str, *, mode: str = MODE_EXPERIENCE) -> str:
    resolved_mode = normalize_private_mode(mode)
    lines = [str(slot_text or "").strip() or "本机当前正被其他内容任务占用，暂时不能开始新的任务。", "", "当前这条请求还没有进入队列。"]
    if resolved_mode == MODE_DEVELOPER:
        lines.extend(
            [
                "说明：",
                "1. 请等待当前本地任务结束后，再重新发送场景稿或“注入场景稿”",
                "2. 如果你只是想看 QQ 侧状态，请发送“状态”或“/s”",
                "3. 这次不会占用你的开发者注入名额，也不会覆盖你已有任务",
            ]
        )
        return "\n".join(lines)
    lines.extend(
        [
            "说明：",
            "1. 请等待当前本地任务结束后，再重新发送“生成”或“/g”",
            "2. 如果你只是想看 QQ 侧状态，请发送“状态”或“/s”",
            "3. 这次不会进入队列，也不会替换你已有任务",
        ]
    )
    return "\n".join(lines)


def build_unknown_command_text(trigger_command: str, help_command: str, status_command: str, *, mode: str) -> str:
    resolved_mode = normalize_private_mode(mode)
    if resolved_mode == MODE_DEVELOPER:
        return "\n".join(
            [
                "没有识别这条指令。",
                "",
                "当前是开发者模式。你可以直接发送：",
                "发送：注入场景稿",
                f"发送：{status_command}",
                f"发送：{help_command}",
                "发送：体验者模式",
                "",
                "如果你正在准备场景稿，请先发送“注入场景稿”或“/i”，再发送正文或 JSON。",
            ]
        )
    return "\n".join(
        [
            "没有识别这条指令。",
            "",
            "当前是体验者模式。你可以直接发送：",
            f"发送：{trigger_command}",
            f"发送：{status_command}",
            f"发送：{help_command}",
            "发送：开发者模式",
            "",
            "如果你是照着帮助消息输入，请不要带引号、序号或句号。",
            "如果你只是想正常使用，直接发送“生成”就可以。",
        ]
    )


def build_wrong_mode_command_text(
    *,
    current_mode: str,
    trigger_command: str,
    help_command: str,
    status_command: str,
) -> str:
    resolved_mode = normalize_private_mode(current_mode)
    if resolved_mode == MODE_DEVELOPER:
        return "\n".join(
            [
                "这条命令属于体验者模式，当前仍处于开发者模式。",
                "",
                "如果你想继续注入测试：直接发送场景设计内容即可。",
                "如果你想先看进度：发送“状态”或“/s”。",
                "如果你想退出开发者模式：发送“体验者模式”或“/e”。",
                f"退出后再发送：{trigger_command} 或 /g",
                f"帮助指令：{help_command} 或 /h",
            ]
        )
    return "\n".join(
        [
            "这条命令属于开发者模式，当前仍处于体验者模式。",
            "",
            "如果你想进入开发者模式：发送“开发者模式”或“/d”。",
            "切换成功后，再发送“注入场景稿”或“/i”。",
            f"如果你只是想正常使用：发送：{trigger_command} 或 /g",
            f"查看进度：发送：{status_command} 或 /s",
            f"查看帮助：发送：{help_command} 或 /h",
        ]
    )


def build_developer_continue_hint_text() -> str:
    return "\n".join(
        [
            "这轮场景稿测试已完成。",
            "",
            "当前仍处于开发者模式，而且会继续保持注入态。",
            "如果你还要继续测试，直接发送新的场景设计内容或 JSON 就可以。",
            "只有发送“体验者模式”或“/e”，才会退出开发者模式。",
        ]
    )


def developer_scene_draft_template() -> str:
    return json.dumps(
        {
            "scenePremiseZh": "旧书店阁楼里的午后魔法",
            "worldSceneZh": "午后的旧书店阁楼里，主角踮脚从高处木书架抽出一本蒙尘厚书，阳光穿过斜顶小窗照在书页与漂浮灰尘上，画面安静而带一点发现秘密时的轻微紧张感。",
        },
        ensure_ascii=False,
        indent=2,
    )


def build_status_text_from_payload(payload: dict[str, Any], *, mode: str | None = None) -> str:
    status = str(payload.get("status", "")).strip() or "unknown"
    stage = normalize_stage_label(str(payload.get("stage", "")).strip())
    run_id = str(payload.get("runId", "")).strip()
    queued_count = int(payload.get("queuedCount", 0) or 0)
    queue_position = int(payload.get("queuePosition", 0) or 0)
    queue_size = int(payload.get("queueSize", queued_count) or 0)
    error = str(payload.get("error", "")).strip()
    mode_label = "开发者模式" if normalize_private_mode(mode or str(payload.get("mode", ""))) == MODE_DEVELOPER else "体验者模式"

    if status == "idle" and queue_position > 0:
        status = "queued"
    if status == "idle":
        return f"当前空闲，处于{mode_label}。"
    if status == "queued":
        if queue_position > 0:
            size_text = f"（共 {queue_size} 个待处理任务）" if queue_size > 0 else ""
            return f"任务已经排队，处于{mode_label}。队列位置：第 {queue_position} 位{size_text}。"
        return f"任务已经排队，处于{mode_label}，队列中共有 {queued_count} 个待处理任务。"
    if status == "running":
        queue_hint = ""
        if queue_position > 0:
            size_text = f"（共 {queue_size} 个待处理任务）" if queue_size > 0 else ""
            queue_hint = f"。你还有一条待处理请求，排在第 {queue_position} 位{size_text}"
        if run_id:
            return f"当前正在生图中，处于{mode_label}。runId: {run_id}。阶段：{stage}{queue_hint}"
        return f"当前正在生图中，处于{mode_label}。阶段：{stage}{queue_hint}"
    if status == "busy_other":
        if queued_count > 0:
            return f"系统当前正在处理其他用户的任务，处于{mode_label}。你当前没有待处理请求，队列中还有 {queued_count} 个待处理任务。"
        return f"系统当前正在处理其他用户的任务，处于{mode_label}。你当前没有待处理请求。"
    if status == "reconnecting":
        return f"当前正在重连 QQ 网关，处于{mode_label}。"
    if status == "error":
        if run_id:
            return f"上一轮失败，处于{mode_label}。runId: {run_id}。错误：{error[:80]}"
        return f"上一轮失败，处于{mode_label}。错误：{error[:80]}"
    return f"当前状态：{status}，处于{mode_label}。"


def parse_status_payload(raw_json: str) -> dict[str, Any]:
    return json.loads(raw_json)
