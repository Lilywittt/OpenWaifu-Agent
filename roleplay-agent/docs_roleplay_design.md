# Roleplay Design

## 产品结构

Roleplay Agent 的主体验是“创造你的角色”。用户可以管理多个角色，每个角色由可自由增删改的内容块组成。界面提供推荐内容块作为初始结构，用户在内容里直接写自然语言。

角色名同时用于左侧角色栏、右侧创作视图和最终模型上下文。保存后的角色配置会被 QQ 发布出口按当前激活角色读取。

## 对话上下文

最终发给模型的内容由以下来源组成：

```text
prompts/system.md
prompts/dialogue_policy.md
prompts/session_profile.md
characters/<active>.json
personas/default.json
events/active_events.json
lorebooks/default.json
runtime/conversations/<user>.jsonl
runtime/memory/<user>.json
prompts/post_history_instructions.md
```

配置界面可以编辑所有进入模型上下文的静态内容：角色、用户设定、临时事件、世界书和 prompt 片段。运行时对话历史与记忆由服务维护。

## 角色管理

角色删除采用二段式流程：用户先确认删除，服务将角色移入回收站；回收站里可以恢复，也可以永久删除。软删除通过角色文件的 `metadata.deletedAt` 标记完成，角色索引会同步移除该角色。

新增角色和复制角色会生成独立 JSON 文件。角色排序由 `config/characters.json` 管理，正文不堆入索引文件。

## 对话与生图路由

QQ 发布出口默认进入角色聊天。用户发出系统指令后进入生图状态；退出指令会回到聊天状态。路由状态按 QQ 用户维度保存在 `runtime/users/`。
