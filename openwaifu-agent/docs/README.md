# 文档索引

这份索引是当前模块的文档入口。以后加功能、改路径、改公网接入，都先按这里的分类落文档。

按这个顺序读：

1. [usage.md](./usage.md)
   当前模块怎么启动、有哪些入口、固定端口是什么。
2. [environment_setup.md](./environment_setup.md)
   `.env`、ComfyUI、本地依赖、工作区路径规则。
3. [directory_management.md](./directory_management.md)
   工作区根、模块根、`.local` 根、`runtime` 根的职责边界。
4. [product_architecture.md](./product_architecture.md)
   产品入口、共享 workbench、QQ、运维之间的架构关系。
5. [content_workbench.md](./content_workbench.md)
   私有测试工作台说明。
6. [public_workbench.md](./public_workbench.md)
   体验工作台和公网接入说明。
7. [ops_dashboard.md](./ops_dashboard.md)
   运维面板说明。
8. [qq_bot_private_service.md](./qq_bot_private_service.md)
   QQ 私聊链路说明。
9. [technical_strategy.md](./technical_strategy.md)
   历史策略文档，只在需要回看决策背景时阅读。

改文档时按这个规则落位：

- 启动方式、端口、入口变化，改 `usage.md`
- `.env`、ComfyUI、路径规则变化，改 `environment_setup.md`
- 目录层级、运行态、持久化路径变化，改 `directory_management.md`
- 公网接入、Tunnel、Access、体验工作台能力边界变化，改 `public_workbench.md`
- 工作台或运维页面行为变化，改对应页面文档

模块级说明集中在 `docs/`，根级说明集中在仓库根目录和模块根目录。
