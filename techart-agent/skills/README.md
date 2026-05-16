# Skills

这里记录 Codex skill 对接 `techart-agent` 的入口约定。

Skill 应通过公开 API 或 CLI 创建任务、生成 handoff 包、导入结果和写入审图记录。Skill 不直接改写业务 Prompt 正文，也不绕过后端接口篡改角色资产。
