# 产品架构说明

这个项目现在分成三层：内容生产核心、公共产品入口、私有工具入口。内容生产核心还是原来的 `creative -> social_post -> prompt_builder -> prompt_guard -> execution -> publish`。公共入口有两条：`QQ` 和 `public workbench`。私有工具入口有两条：`运维面板` 和 `内容测试工作台`。

`QQ` 和 `public workbench` 不是同一类业务。`QQ` 是窄入口，负责消息触发和回传；`public workbench` 是 richer 的交互式网页入口，能力接近工作台，允许选择起点、终点并查看阶段产物。因为这条 richer 业务和私有测试工作台本质相同，所以两者共用 `src/workbench/` 这一套共享内核。

整体关系就是：

```text
内容生产核心
  -> creative
  -> social_post
  -> prompt_builder
  -> prompt_guard
  -> execution
  -> publish

共享 workbench 内核
  -> private studio workbench
  -> public workbench

QQ 产品入口
  -> publish

运维工具
  -> ops dashboard
```

目录上对应这几块：`src/workbench/` 是共享 workbench 内核，`src/studio/` 是私有 workbench 适配层，`src/public_web/` 是公共 workbench 适配层，`src/ops/` 是运维面板，`src/publish/` 是 QQ 产品入口。

`public workbench` 和私有工作台的差别不在任务链，而在权限和身份。私有模式保留目录审阅、收藏、删目录、cleanup 这些系统级能力；公共模式保留发起任务、查看状态、查看阶段产物、查看结果，并且所有历史和详情都按 `ownerId` 做隔离。`ownerId` 由 `Cloudflare Access` 登录身份解析而来。
