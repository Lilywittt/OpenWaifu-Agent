# openwaifu-agent

这是当前产品模块。它来自原 `ig_roleplay_v3`，但现在已经作为总仓库下的独立模块存在。

文档入口就在这个 README。

常用入口：

```powershell
python run_product.py
python run_generate_product.py --run-label generate_test
python run_qq_bot_service.py start
python run_ops_dashboard.py
python run_content_workbench.py
python run_public_workbench.py
```

固定端口：

- 运维面板：`8765`
- 私有测试工作台：`8766`
- 体验工作台：`8767`

核心配置入口：

- `config/character_assets.json`
- `config/llm_profiles.json`
- `config/workbench_profiles.json`
- `config/execution/active_profile.json`

目录抓手：

- `src/workbench/`：共享 workbench 内核
- `src/studio/`：私有测试入口适配层
- `src/public_web/`：体验工作台入口适配层
- `src/ops/`：运维面板
- `src/publish/`：QQ 产品入口
- `tools/remote_access/`：当前模块自己的公网接入脚本

文档定位：

- 启动方式、端口、入口：[docs/usage.md](./docs/usage.md)
- 环境、`.env`、ComfyUI、本地依赖：[docs/environment_setup.md](./docs/environment_setup.md)
- 目录、路径和运行态管理：[docs/directory_management.md](./docs/directory_management.md)
- 产品结构和入口关系：[docs/product_architecture.md](./docs/product_architecture.md)
- 私有测试工作台：[docs/content_workbench.md](./docs/content_workbench.md)
- 体验工作台和公网接入：[docs/public_workbench.md](./docs/public_workbench.md)
- 运维面板：[docs/ops_dashboard.md](./docs/ops_dashboard.md)
- QQ 私聊链路：[docs/qq_bot_private_service.md](./docs/qq_bot_private_service.md)
- 历史技术策略：[docs/technical_strategy.md](./docs/technical_strategy.md)
