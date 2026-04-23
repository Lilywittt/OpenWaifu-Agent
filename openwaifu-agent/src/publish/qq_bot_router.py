from __future__ import annotations

from typing import Any

from .qq_bot_private_state import DEFAULT_PENDING_ACTION, PENDING_ACTION_SCENE_DRAFT
from .qq_bot_private_ui import (
    MODE_DEVELOPER,
    MODE_EXPERIENCE,
    build_developer_input_received_text,
    build_developer_input_text,
    build_developer_pending_text,
    build_help_text as build_help_text_ui,
    build_mode_switched_text,
    build_started_text as build_started_text_ui,
    build_unknown_command_text,
    build_wrong_mode_command_text,
    normalize_private_mode,
)
from .qq_bot_scene_draft import parse_scene_draft_message


DEFAULT_TRIGGER_COMMAND = "生成"
DEFAULT_HELP_COMMAND = "帮助"
DEFAULT_STATUS_COMMAND = "状态"
DEFAULT_EXPERIENCE_MODE_COMMAND = "体验者模式"
DEFAULT_DEVELOPER_MODE_COMMAND = "开发者模式"
DEFAULT_DEVELOPER_SCENE_COMMAND = "注入场景稿"
COMMAND_ALIASES = {
    DEFAULT_TRIGGER_COMMAND: {DEFAULT_TRIGGER_COMMAND, "/g"},
    DEFAULT_STATUS_COMMAND: {DEFAULT_STATUS_COMMAND, "/s"},
    DEFAULT_HELP_COMMAND: {DEFAULT_HELP_COMMAND, "/h"},
    DEFAULT_DEVELOPER_MODE_COMMAND: {DEFAULT_DEVELOPER_MODE_COMMAND, "/d"},
    DEFAULT_EXPERIENCE_MODE_COMMAND: {DEFAULT_EXPERIENCE_MODE_COMMAND, "/e"},
    DEFAULT_DEVELOPER_SCENE_COMMAND: {DEFAULT_DEVELOPER_SCENE_COMMAND, "/i"},
}
COMMAND_WRAPPING_QUOTES = "\"'“”‘’「」『』`"
COMMAND_TRAILING_PUNCTUATION = "。！？!?，,、；;：:~～…"


def normalize_message_text(content: str) -> str:
    return str(content or "").replace("\u3000", " ").strip()


def canonicalize_command_text(content: str) -> str:
    normalized = normalize_message_text(content)
    if not normalized:
        return ""

    previous = None
    current = normalized
    while previous != current:
        previous = current
        current = current.strip()
        if len(current) >= 2 and current[0] in COMMAND_WRAPPING_QUOTES and current[-1] in COMMAND_WRAPPING_QUOTES:
            current = current[1:-1].strip()
        while current and current[-1] in COMMAND_TRAILING_PUNCTUATION:
            current = current[:-1].rstrip()
    return current


def matches_command_alias(command_text: str, canonical_command: str, *extra_aliases: str) -> bool:
    allowed = set(COMMAND_ALIASES.get(canonical_command, {canonical_command}))
    allowed.update(str(alias or "").strip() for alias in extra_aliases if str(alias or "").strip())
    return command_text in allowed


def is_known_command_alias(command_text: str, *extra_aliases: str) -> bool:
    if not command_text:
        return False
    for canonical_command in COMMAND_ALIASES:
        if matches_command_alias(command_text, canonical_command, *extra_aliases):
            return True
    return False


def interpret_private_message(
    *,
    content: str,
    user_mode: str,
    pending_action: str,
    status_text: str,
    trigger_command: str = DEFAULT_TRIGGER_COMMAND,
    help_command: str = DEFAULT_HELP_COMMAND,
    status_command: str = DEFAULT_STATUS_COMMAND,
) -> dict[str, Any]:
    normalized_content = normalize_message_text(content)
    command_text = canonicalize_command_text(content)
    resolved_mode = normalize_private_mode(user_mode)
    resolved_pending_action = str(pending_action or "").strip()

    if matches_command_alias(command_text, DEFAULT_HELP_COMMAND, help_command):
        return {
            "kind": "help",
            "replyText": build_help_text_ui(trigger_command, help_command, status_command, mode=resolved_mode),
            "nextMode": resolved_mode,
            "nextPendingAction": resolved_pending_action,
        }
    if matches_command_alias(command_text, DEFAULT_STATUS_COMMAND, status_command):
        return {
            "kind": "status",
            "replyText": status_text,
            "nextMode": resolved_mode,
            "nextPendingAction": resolved_pending_action,
        }
    if matches_command_alias(command_text, DEFAULT_DEVELOPER_MODE_COMMAND):
        if resolved_mode == MODE_DEVELOPER:
            return {
                "kind": "same_mode_guidance",
                "replyText": (
                    build_developer_input_text()
                    if resolved_pending_action == PENDING_ACTION_SCENE_DRAFT
                    else build_mode_switched_text(MODE_DEVELOPER)
                ),
                "nextMode": MODE_DEVELOPER,
                "nextPendingAction": resolved_pending_action,
            }
        return {
            "kind": "switch_mode",
            "replyText": build_mode_switched_text(MODE_DEVELOPER),
            "nextMode": MODE_DEVELOPER,
            "nextPendingAction": DEFAULT_PENDING_ACTION,
        }
    if matches_command_alias(command_text, DEFAULT_EXPERIENCE_MODE_COMMAND):
        if resolved_mode == MODE_EXPERIENCE:
            return {
                "kind": "same_mode_guidance",
                "replyText": build_mode_switched_text(MODE_EXPERIENCE),
                "nextMode": MODE_EXPERIENCE,
                "nextPendingAction": resolved_pending_action,
            }
        return {
            "kind": "switch_mode",
            "replyText": build_mode_switched_text(MODE_EXPERIENCE),
            "nextMode": MODE_EXPERIENCE,
            "nextPendingAction": DEFAULT_PENDING_ACTION,
        }
    if resolved_mode == MODE_DEVELOPER and matches_command_alias(command_text, DEFAULT_DEVELOPER_SCENE_COMMAND):
        return {
            "kind": "developer_scene_prompt",
            "replyText": build_developer_input_text(),
            "nextMode": MODE_DEVELOPER,
            "nextPendingAction": PENDING_ACTION_SCENE_DRAFT,
        }
    if resolved_mode == MODE_EXPERIENCE and matches_command_alias(command_text, DEFAULT_TRIGGER_COMMAND, trigger_command):
        return {
            "kind": "trigger_generation",
            "replyText": build_started_text_ui(mode=resolved_mode),
            "nextMode": resolved_mode,
            "nextPendingAction": resolved_pending_action,
        }
    if resolved_mode == MODE_EXPERIENCE and matches_command_alias(command_text, DEFAULT_DEVELOPER_SCENE_COMMAND):
        return {
            "kind": "wrong_mode_command",
            "replyText": build_wrong_mode_command_text(
                current_mode=resolved_mode,
                trigger_command=trigger_command,
                help_command=help_command,
                status_command=status_command,
            ),
            "nextMode": resolved_mode,
            "nextPendingAction": resolved_pending_action,
        }
    if resolved_mode == MODE_DEVELOPER and matches_command_alias(command_text, DEFAULT_TRIGGER_COMMAND, trigger_command):
        return {
            "kind": "wrong_mode_command",
            "replyText": build_wrong_mode_command_text(
                current_mode=resolved_mode,
                trigger_command=trigger_command,
                help_command=help_command,
                status_command=status_command,
            ),
            "nextMode": resolved_mode,
            "nextPendingAction": resolved_pending_action,
        }
    if command_text and is_known_command_alias(command_text, trigger_command, help_command, status_command):
        return {
            "kind": "unknown",
            "replyText": build_unknown_command_text(
                trigger_command,
                help_command,
                status_command,
                mode=resolved_mode,
            ),
            "nextMode": resolved_mode,
            "nextPendingAction": resolved_pending_action,
        }
    if resolved_pending_action == PENDING_ACTION_SCENE_DRAFT:
        if not normalized_content:
            return {
                "kind": "awaiting_scene_draft",
                "replyText": build_developer_pending_text(),
                "nextMode": resolved_mode,
                "nextPendingAction": PENDING_ACTION_SCENE_DRAFT,
            }
        try:
            scene_draft = parse_scene_draft_message(normalized_content)
        except Exception as exc:
            return {
                "kind": "invalid_scene_draft",
                "replyText": "\n".join(
                    [
                        "场景设计稿格式不正确",
                        "",
                        str(exc),
                        "",
                        build_developer_input_text(),
                    ]
                ),
                "nextMode": resolved_mode,
                "nextPendingAction": PENDING_ACTION_SCENE_DRAFT,
            }
        return {
            "kind": "scene_draft_submission",
            "replyText": build_developer_input_received_text(scene_draft.get("scenePremiseZh", "")),
            "sceneDraft": scene_draft,
            "nextMode": resolved_mode,
            "nextPendingAction": PENDING_ACTION_SCENE_DRAFT,
        }
    return {
        "kind": "unknown",
        "replyText": build_unknown_command_text(
            trigger_command,
            help_command,
            status_command,
            mode=resolved_mode,
        ),
        "nextMode": resolved_mode,
        "nextPendingAction": resolved_pending_action,
    }
