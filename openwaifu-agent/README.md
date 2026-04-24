# openwaifu-agent

当前产品模块就在这个目录下运行。

常用入口：
```powershell
python run_product.py
python run_generate_product.py --run-label generate_test
python run_qq_bot_service.py start
python run_ops_dashboard.py
python run_content_workbench.py
python run_public_workbench.py
python run_workbench_report_service.py start
```

固定端口：
- 运维面板：`8765`
- 私有测试工作台：`8766`
- 内容体验工作台：`8767`

核心配置：
- `config/character_assets.json`
- `config/llm_profiles.json`
- `config/workbench_profiles.json`
- `config/execution/active_profile.json`

目录抓手：
- `src/workbench/`：共享 workbench 内核
- `src/studio/`：私有测试工作台入口
- `src/public_web/`：内容体验工作台入口
- `src/ops/`：运维面板
- `src/publish/`：QQ 产品链与社媒发布能力
- `src/reporting/`：workbench 结果监听与 QQ 极简报告
- `tools/remote_access/`：公网接入脚本

文档入口：
- [docs/usage.md](./docs/usage.md)
- [docs/environment_setup.md](./docs/environment_setup.md)
- [docs/directory_management.md](./docs/directory_management.md)
- [docs/product_architecture.md](./docs/product_architecture.md)
- [docs/content_workbench.md](./docs/content_workbench.md)
- [docs/public_workbench.md](./docs/public_workbench.md)
- [docs/workbench_report_service.md](./docs/workbench_report_service.md)
- [docs/ops_dashboard.md](./docs/ops_dashboard.md)
- [docs/qq_bot_private_service.md](./docs/qq_bot_private_service.md)
- [docs/technical_strategy.md](./docs/technical_strategy.md)
