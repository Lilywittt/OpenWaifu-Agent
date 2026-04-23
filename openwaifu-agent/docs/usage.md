# 使用说明

所有入口都在当前模块根目录运行。

```powershell
cd <repo-root>\openwaifu-agent
```

常用入口：

```powershell
python run_qq_bot_service.py start
python run_ops_dashboard.py
python run_content_workbench.py
python run_public_workbench.py
python run_product.py
```

端口固定为：

- 运维面板：`8765`
- 私有测试工作台：`8766`
- 体验工作台：`8767`

`run_content_workbench.py` 是私有测试入口，保留目录审阅、收藏、删除和清理能力。`run_public_workbench.py` 是体验工作台入口，保留 richer 的生成与产物查看能力，但裁掉系统级动作。`run_qq_bot_service.py` 继续控制 QQ 服务。

环境变量、本地资源和路径规则统一看 [`environment_setup.md`](./environment_setup.md)。体验工作台的公网接入统一看 [`public_workbench.md`](./public_workbench.md)。完整文档索引在 [`README.md`](./README.md)。
