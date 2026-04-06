from __future__ import annotations

from typing import Any


KEY_TO_CN = {
    "meta": "元信息",
    "createdAt": "创建时间",
    "stage": "阶段",
    "defaultRunContext": "默认运行上下文",
    "runMode": "运行模式",
    "nowLocal": "当前本地时间",
    "worldDesignInput": "场景稿输入包",
    "sceneToDesignInput": "场景派生输入包",
    "subjectCore": "人物摘要",
    "displayNameZh": "人物显示名",
    "identityCoreZh": "身份内核",
    "faceCoreZh": "脸部内核",
    "hairCoreZh": "头发与识别线索",
    "bodyCoreZh": "身体内核",
    "realityBoundariesZh": "人物边界",
    "socialSignalSample": "随机社媒采样",
    "sourceKey": "社媒来源标识",
    "sourceZh": "社媒来源",
    "providerKey": "来源标识",
    "providerZh": "来源名称",
    "sampledSignalsZh": "采样内容",
    "subjectProfile": "人物固有资产",
    "worldDesign": "场景稿",
    "sceneDraft": "场景稿",
    "actionDesign": "动作设计稿",
    "wardrobeDesign": "服装设计稿",
    "cameraDesign": "镜头设计稿",
    "scenePremiseZh": "场景命题",
    "worldSceneZh": "场景正文",
    "actionSummaryZh": "动作摘要",
    "momentZh": "动作瞬间",
    "bodyActionZh": "身体动作",
    "mustReadZh": "动作要点",
    "forbiddenDriftZh": "禁止漂移",
    "notesZh": "备注",
    "wardrobeSummaryZh": "服装摘要",
    "requiredZh": "必需项",
    "optionalZh": "可选项",
    "forbiddenZh": "禁止项",
    "cameraSummaryZh": "镜头摘要",
    "framing": "景别",
    "aspectRatio": "画幅比例",
    "angleZh": "机位角度",
    "compositionGoalZh": "构图目标",
    "mustIncludeZh": "必须包含",
    "renderPacket": "出图转录包",
    "summaryZh": "总结",
    "subject": "人物",
    "identityReadZh": "人物读感",
    "facts": "事实条目",
    "forbidden": "禁止条目",
    "world": "世界",
    "action": "动作",
    "wardrobe": "服装",
    "required": "必需条目",
    "optional": "可选条目",
    "camera": "镜头",
    "integration": "整合裁决",
    "heroFactIds": "主事实编号",
    "supportingFactIds": "辅助事实编号",
    "negativeFactIds": "负向事实编号",
    "conflictResolutionsZh": "裁决说明",
    "renderIntentZh": "出图侧重点",
    "acceptanceChecksZh": "验收检查项",
    "id": "编号",
    "textZh": "中文事实",
    "subject_id": "人物标识",
    "display_name_zh": "人物显示名",
    "identity_truth": "身份事实",
    "life_stage_zh": "人生阶段",
    "gender_read_zh": "性别读感",
    "age_read_zh": "年龄读感",
    "face_truth": "脸部事实",
    "shape_zh": "脸型特征",
    "age_signal_zh": "脸部年龄信号",
    "hair_truth": "头发事实",
    "color_family_zh": "发色家族",
    "length_zh": "发长",
    "style_zh": "发型",
    "signature_markers_zh": "固定识别物",
    "body_truth": "身体事实",
    "build_zh": "体型",
    "maturity_zh": "成熟度",
    "proportion_zh": "身体比例",
    "allowed_changes_zh": "允许的临时人物改动",
    "forbidden_drift_zh": "禁止漂移项",
    "positiveFacts": "正向事实条目",
    "negativeFacts": "负向事实条目",
    "stylePositiveEn": "通用正向英文风格",
    "genericNegativeEn": "通用负向英文风格",
    "workflow": "工作流",
    "provider": "提供方",
    "seed": "随机种子",
    "section": "所属分支",
    "positiveCuesEn": "正向英文短句",
    "negativeCuesEn": "负向英文短句",
    "phraseEn": "英文短句",
}

CN_TO_KEY = {value: key for key, value in KEY_TO_CN.items()}

VALUE_TO_CN = {
    "default": "默认运行",
    "simulate": "模拟运行",
    "full_body": "全身",
    "half_body": "半身",
    "close_up": "近景",
    "subject": "人物",
    "world": "世界",
    "action": "动作",
    "wardrobe": "服装",
    "camera": "镜头",
    "subject_forbidden": "人物禁止项",
    "world_forbidden": "世界禁止项",
    "action_forbidden": "动作禁止项",
    "wardrobe_forbidden": "服装禁止项",
    "wardrobe_optional": "服装可选项",
    "camera_forbidden": "镜头禁止项",
    "comfyui-local-anime": "本地 ComfyUI 动漫工作流",
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
