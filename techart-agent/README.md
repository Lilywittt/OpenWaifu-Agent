# techart-agent

`techart-agent` 是面向 B 端技术美术生产的图片资产效率工具。它围绕项目资产、角色标准、生成任务、工作流执行、质量验收、资产入库和批量导出组织能力，用于提高 galgame 美术图片生产效率。

当前阶段先搭产品骨架和数据契约。后续实现代码时，所有页面、脚本和生成后端都围绕这些契约扩展。

## 核心链路

```text
项目资产
  -> 美术任务
  -> 角色与画风约束
  -> 候选图生成
  -> 人工挑选
  -> 精修与局部修复
  -> 质量验收
  -> 入库与导出
  -> 反馈数据沉淀
```

## 目录

```text
techart-agent/
  config/      产品配置、资产类型、导出规格、工作流预设
  docs/        架构说明、数据契约和实施计划
  prompts/     业务 Prompt 文件，由项目负责人维护正文
  projects/    项目资产根目录，本地项目数据默认本地管理
  runtime/     本地运行态、缓存和临时产物
  src/         后续产品代码
  tools/       检查、导入、导出和维护脚本
```

## 文档入口

- [产品架构](./docs/product_architecture.md)
- [目录结构](./docs/directory_layout.md)
- [角色资产库](./docs/character_asset_library.md)
- [任务契约](./docs/task_contract.md)
- [工作流契约](./docs/workflow_contract.md)
- [Prompt 治理](./docs/prompt_governance.md)
- [审图反馈](./docs/review_feedback.md)
