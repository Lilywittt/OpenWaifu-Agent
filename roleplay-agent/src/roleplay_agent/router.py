from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import load_command_config
from .io_utils import read_json, write_json
from .paths import safe_segment


MODE_CHAT = "chat"
MODE_IMAGE = "image"
PENDING_NONE = ""
PENDING_IMAGE_SCENE = "image_scene"

COMMAND_WRAPPING_QUOTES = "\"'“”‘’「」『』`"
COMMAND_TRAILING_PUNCTUATION = "。！？!?，,、；;：:~～…"


@dataclass(frozen=True)
class RouteResult:
    kind: str
    reply_text: str = ""
    next_mode: str = MODE_CHAT
    next_pending: str = PENDING_NONE
    payload: dict[str, Any] | None = None


def user_state_path(project_dir: Path, user_id: str) -> Path:
    return project_dir / "runtime" / "users" / f"{safe_segment(user_id)}.json"


def load_user_state(project_dir: Path, user_id: str) -> dict[str, Any]:
    payload = read_json(user_state_path(project_dir, user_id), default={})
    if not isinstance(payload, dict):
        payload = {}
    mode = str(payload.get("mode", MODE_CHAT)).strip()
    pending = str(payload.get("pendingAction", PENDING_NONE)).strip()
    if mode not in {MODE_CHAT, MODE_IMAGE}:
        mode = MODE_CHAT
    return {"mode": mode, "pendingAction": pending}


def save_user_state(project_dir: Path, user_id: str, *, mode: str, pending_action: str = PENDING_NONE) -> None:
    write_json(
        user_state_path(project_dir, user_id),
        {
            "mode": mode if mode in {MODE_CHAT, MODE_IMAGE} else MODE_CHAT,
            "pendingAction": str(pending_action or "").strip(),
        },
    )


def normalize_message_text(content: str) -> str:
    return str(content or "").replace("\u3000", " ").strip()


def canonicalize_command_text(content: str) -> str:
    current = normalize_message_text(content)
    if not current:
        return ""
    previous = None
    while previous != current:
        previous = current
        current = current.strip()
        if len(current) >= 2 and current[0] in COMMAND_WRAPPING_QUOTES and current[-1] in COMMAND_WRAPPING_QUOTES:
            current = current[1:-1].strip()
        while current and current[-1] in COMMAND_TRAILING_PUNCTUATION:
            current = current[:-1].rstrip()
    return current


def _matches(commands: dict[str, list[str]], key: str, command_text: str) -> bool:
    return bool(command_text and command_text in set(commands.get(key, [])))


def _help_text(commands: dict[str, list[str]], mode: str) -> str:
    enter_image = commands.get("enterImageMode", ["系统指令"])[0]
    exit_image = commands.get("exitImageMode", ["退出系统指令"])[0]
    image_generate = commands.get("imageGenerate", ["生成"])[0]
    image_scene = commands.get("imageScenePrompt", ["注入场景稿"])[0]
    if mode == MODE_IMAGE:
        return "\n".join(
            [
                "当前是系统指令态。",
                f"{image_generate}：执行默认生图",
                f"{image_scene}：提交场景稿生图",
                f"{exit_image}：回到角色聊天",
            ]
        )
    return "\n".join(
        [
            "当前是角色聊天。",
            "直接发消息：和角色聊天",
            f"{enter_image}：进入系统指令态",
            "状态：查看当前模式",
            "重置对话：清空当前私聊历史",
        ]
    )


def _status_text(mode: str, pending: str) -> str:
    mode_text = "系统指令态" if mode == MODE_IMAGE else "角色聊天"
    if pending == PENDING_IMAGE_SCENE:
        return f"当前模式：{mode_text}\n等待场景稿输入。"
    return f"当前模式：{mode_text}"


def looks_like_scene_draft(text: str) -> bool:
    stripped = normalize_message_text(text)
    if not stripped:
        return False
    if stripped.startswith("{") or stripped.startswith("["):
        return True
    return bool(re.search(r"(scenePremiseZh|场景|镜头|画面|角色|构图|prompt)", stripped, flags=re.IGNORECASE))


def interpret_message(
    *,
    project_dir: Path,
    user_id: str,
    content: str,
    image_bridge_status: str = "",
) -> RouteResult:
    commands = load_command_config(project_dir)
    state = load_user_state(project_dir, user_id)
    mode = str(state.get("mode", MODE_CHAT))
    pending = str(state.get("pendingAction", PENDING_NONE))
    normalized = normalize_message_text(content)
    command_text = canonicalize_command_text(content)

    if _matches(commands, "help", command_text):
        return RouteResult("help", _help_text(commands, mode), mode, pending)
    if _matches(commands, "status", command_text):
        extra = str(image_bridge_status or "").strip()
        text = _status_text(mode, pending)
        if extra:
            text = f"{text}\n{extra}"
        return RouteResult("status", text, mode, pending)
    if _matches(commands, "resetConversation", command_text):
        return RouteResult("reset_conversation", "对话历史已重置。", mode, pending)
    if _matches(commands, "reloadConfig", command_text):
        return RouteResult("reload_config", "配置会在下一条消息自动重新读取。", mode, pending)
    if _matches(commands, "enterImageMode", command_text):
        return RouteResult(
            "enter_image_mode",
            "已进入系统指令态。发送“生成”开始默认生图，发送“注入场景稿”后继续提交场景稿。",
            MODE_IMAGE,
            PENDING_NONE,
        )
    if _matches(commands, "exitImageMode", command_text):
        return RouteResult("exit_image_mode", "已回到角色聊天。", MODE_CHAT, PENDING_NONE)

    if mode == MODE_IMAGE:
        if _matches(commands, "imageScenePrompt", command_text):
            return RouteResult(
                "image_scene_prompt",
                "请发送场景稿。可以用 JSON，也可以用清晰的中文描述。",
                MODE_IMAGE,
                PENDING_IMAGE_SCENE,
            )
        if _matches(commands, "imageGenerate", command_text):
            return RouteResult("image_generate", "已接收默认生图请求。", MODE_IMAGE, PENDING_NONE)
        if pending == PENDING_IMAGE_SCENE:
            if normalized:
                return RouteResult(
                    "image_scene_submit",
                    "已接收场景稿生图请求。",
                    MODE_IMAGE,
                    PENDING_IMAGE_SCENE,
                    {"sceneText": normalized},
                )
            return RouteResult("image_scene_prompt", "请继续发送场景稿。", MODE_IMAGE, PENDING_IMAGE_SCENE)
        return RouteResult(
            "image_mode_unknown",
            _help_text(commands, MODE_IMAGE),
            MODE_IMAGE,
            pending,
        )

    return RouteResult("chat", next_mode=MODE_CHAT, next_pending=PENDING_NONE, payload={"text": normalized})
