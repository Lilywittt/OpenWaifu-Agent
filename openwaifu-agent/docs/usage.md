# 使用说明

所有入口都在 `openwaifu-agent` 根目录执行。

```powershell
cd <repo-root>\openwaifu-agent
```

常用入口：

```powershell
python run_qq_bot_service.py start
python run_ops_dashboard.py
python run_content_workbench.py
python run_public_workbench.py
python run_workbench_report_service.py start
python run_product.py
```

固定端口：

- 运维面板：`8765`
- 私有测试工作台：`8766`
- 内容体验工作台：`8767`

入口说明：

- `run_content_workbench.py`：私有测试工作台
- `run_public_workbench.py`：内容体验工作台
- `run_ops_dashboard.py`：运维面板
- `run_qq_bot_service.py`：QQ 私聊服务
- `run_workbench_report_service.py`：workbench 结果监听与 QQ 极简报告

相关文档：

- 环境、`.env`、ComfyUI、本地依赖：[environment_setup.md](./environment_setup.md)
- 路径、目录和运行态：[directory_management.md](./directory_management.md)
- 产品结构与入口关系：[product_architecture.md](./product_architecture.md)
- 私有测试工作台：[content_workbench.md](./content_workbench.md)
- 内容体验工作台与公网接入：[public_workbench.md](./public_workbench.md)
- workbench 报告监听服务：[workbench_report_service.md](./workbench_report_service.md)
- 运维面板：[ops_dashboard.md](./ops_dashboard.md)
- QQ 私聊链路：[qq_bot_private_service.md](./qq_bot_private_service.md)
