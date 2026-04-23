from __future__ import annotations

from typing import Any


KEY_TO_CN = {
    "meta": "元信息",
    "createdAt": "创建时间",
    "stage": "阶段",
    "defaultRunContext": "默认运行上下文",
    "runMode": "运行模式",
    "nowLocal": "当前本地时间",
    "socialSignalFilterInput": "采样过滤输入包",
    "worldDesignInput": "场景设计稿输入包",
    "environmentDesignInput": "环境、布景与光影设计输入包",
    "stylingDesignInput": "服装与造型设计输入包",
    "actionDesignInput": "动作与姿态、神态设计输入包",
    "socialPostInput": "社媒文案输入包",
    "imagePromptInput": "生图Prompt输入包",
    "socialSignalSample": "随机社媒采样",
    "sourceKey": "社媒来源标识",
    "sourceZh": "社媒来源",
    "providerKey": "来源标识",
    "providerZh": "来源名称",
    "sampledSignalsZh": "采样内容",
    "signalCandidates": "采样候选项",
    "selectedSignalId": "选中采样编号",
    "subjectProfile": "原始人物资产",
    "worldDesign": "场景设计稿",
    "sceneDraft": "场景设计稿",
    "environmentDesign": "环境、布景与光影设计稿",
    "stylingDesign": "服装与造型设计稿",
    "actionDesign": "动作与姿态、神态设计稿",
    "socialPostText": "社媒文案",
    "imagePrompt": "生图Prompt",
    "scenePremiseZh": "场景命题",
    "worldSceneZh": "场景正文",
    "notesZh": "备注",
    "requiredZh": "必需项",
    "optionalZh": "可选项",
    "forbiddenZh": "禁止项",
    "mustIncludeZh": "必须包含",
    "id": "编号",
    "textZh": "中文事实",
    "subject_id": "人物标识",
    "display_name_zh": "人物显示名",
    "identity_zh": "身份语义",
    "appearance_zh": "外观语义",
    "psychology_zh": "心理特征",
    "allowed_changes_zh": "允许的临时人物改动",
    "forbidden_drift_zh": "禁止漂移项",
    "notes_zh": "补充说明",
}

CN_TO_KEY = {value: key for key, value in KEY_TO_CN.items()}

VALUE_TO_CN = {
    "default": "默认运行",
    "simulate": "模拟运行",
}

CN_TO_VALUE = {value: key for key, value in VALUE_TO_CN.items()}


def to_deepseek_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {KEY_TO_CN.get(key, key): to_deepseek_payload(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [to_deepseek_payload(item) for item in value]
    if isinstance(value, str):
        return VALUE_TO_CN.get(value, value)
    return value


def from_deepseek_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {CN_TO_KEY.get(key, key): from_deepseek_payload(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [from_deepseek_payload(item) for item in value]
    if isinstance(value, str):
        return CN_TO_VALUE.get(value, value)
    return value
