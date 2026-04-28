from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from llm_schema import to_deepseek_payload


TASK_SECTION_OPEN = "<\u4efb\u52a1\u533a>"
TASK_SECTION_CLOSE = "</\u4efb\u52a1\u533a>"
JSON_SECTION_OPEN = "<\u8fd4\u56de\u683c\u5f0f>"
JSON_SECTION_CLOSE = "</\u8fd4\u56de\u683c\u5f0f>"
TEXT_SECTION_OPEN = "<\u8f93\u51fa\u8981\u6c42>"
TEXT_SECTION_CLOSE = "</\u8f93\u51fa\u8981\u6c42>"
TEXT_NO_JSON = "\u4e0d\u8981\u8f93\u51fa JSON\u3002"
TEXT_NO_EXPLANATION = "\u4e0d\u8981\u89e3\u91ca\u89c4\u5219\u6216\u8865\u5145\u9898\u5916\u8bdd\u3002"
DESIGN_TEXT_INSTRUCTION = "\u76f4\u63a5\u8f93\u51fa\u6700\u7ec8\u8bbe\u8ba1\u7a3f\u6b63\u6587\u3002"
SOCIAL_POST_TEXT_INSTRUCTION = "\u76f4\u63a5\u8f93\u51fa\u6700\u7ec8\u793e\u5a92\u6587\u6848\u6b63\u6587\u3002"
JSON_NOTICE_SPACED = "\u8bf7\u53ea\u8fd4\u56de\u7b26\u5408\u4e0b\u5217\u9aa8\u67b6\u7684\u5408\u6cd5 JSON\u3002"
JSON_NOTICE_COMPACT = "\u8bf7\u53ea\u8fd4\u56de\u7b26\u5408\u4e0b\u5217\u9aa8\u67b6\u7684\u5408\u6cd5JSON\u3002"


@dataclass(frozen=True)
class StageProtocol:
    output_mode: Literal["json", "text"]
    text_instruction: str | None = None
    json_notice: str | None = None


_STAGE_PROTOCOLS: dict[str, StageProtocol] = {
    "creative.social_signal_filter": StageProtocol(
        output_mode="json",
        json_notice=JSON_NOTICE_SPACED,
    ),
    "creative.world_design": StageProtocol(
        output_mode="json",
        json_notice=JSON_NOTICE_SPACED,
    ),
    "creative.environment_design": StageProtocol(
        output_mode="text",
        text_instruction=DESIGN_TEXT_INSTRUCTION,
    ),
    "creative.styling_design": StageProtocol(
        output_mode="text",
        text_instruction=DESIGN_TEXT_INSTRUCTION,
    ),
    "creative.action_design": StageProtocol(
        output_mode="text",
        text_instruction=DESIGN_TEXT_INSTRUCTION,
    ),
    "social_post.default": StageProtocol(
        output_mode="text",
        text_instruction=SOCIAL_POST_TEXT_INSTRUCTION,
    ),
    "prompt_builder.default": StageProtocol(
        output_mode="json",
        json_notice=JSON_NOTICE_COMPACT,
    ),
    "prompt_guard.default": StageProtocol(
        output_mode="json",
        json_notice=JSON_NOTICE_COMPACT,
    ),
}


def build_stage_system_prompt(*, stage_id: str, prompt_text: str, output_contract: Any | None = None) -> str:
    protocol = _STAGE_PROTOCOLS.get(stage_id)
    if protocol is None:
        raise RuntimeError(f"Unknown stage protocol: {stage_id}")

    sections = [
        TASK_SECTION_OPEN,
        prompt_text,
        TASK_SECTION_CLOSE,
    ]

    if protocol.output_mode == "json":
        if output_contract is None:
            raise RuntimeError(f"{stage_id} requires an output contract.")
        output_schema = json.dumps(to_deepseek_payload(output_contract), ensure_ascii=False, indent=2)
        sections.extend(
            [
                JSON_SECTION_OPEN,
                str(protocol.json_notice or "").strip(),
                output_schema,
                JSON_SECTION_CLOSE,
            ]
        )
        return "\n\n".join(sections)

    instruction = str(protocol.text_instruction or "").strip()
    if not instruction:
        raise RuntimeError(f"{stage_id} requires a text instruction.")
    sections.extend(
        [
            TEXT_SECTION_OPEN,
            instruction,
            TEXT_NO_JSON,
            TEXT_NO_EXPLANATION,
            TEXT_SECTION_CLOSE,
        ]
    )
    return "\n\n".join(sections)
