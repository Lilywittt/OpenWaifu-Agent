# 使用说明

所有入口都在项目根目录运行：

```powershell
cd /d F:\openclaw-dev\workspace\projects\ig_roleplay_v3
```

常用入口现在是这五个：

```powershell
python run_qq_bot_service.py start
python run_ops_dashboard.py
python run_content_workbench.py
python run_public_workbench.py
python run_product.py
```

端口固定是：

- 运维面板：`8765`
- 私有工作台：`8766`
- 公共 workbench：`8767`

`run_content_workbench.py` 是私有调试入口，保留目录审阅、收藏、删目录和清理能力。`run_public_workbench.py` 是公共网页入口，保留 richer 的生成与产物查看能力，但按公共权限裁掉系统级动作。`run_qq_bot_service.py` 继续控制 QQ 服务。

公共 workbench 只监听本机 `127.0.0.1:8767`。要给外部体验者访问，用 `Cloudflare Tunnel + Access` 这一层发出去，不要直接把服务绑到 `0.0.0.0`。相关模板和脚本在 [F:\openclaw-dev\workspace\projects\ig_roleplay_v3\tools\remote_access](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/tools/remote_access)。

清理、索引和 richer 的测试控制命令仍然挂在私有工作台入口上：

```powershell
python run_content_workbench.py inventory
python run_content_workbench.py cleanup-report --older-than-days 14
python run_content_workbench.py delete-run --run-id 2026-04-11T21-11-48_01
```

公共 workbench 的公网接入统一看 [F:\openclaw-dev\workspace\projects\ig_roleplay_v3\docs\public_workbench.md](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/docs/public_workbench.md)。公网接入的实际链路、当前脚本行为和健康检查口径，都只以这份主文档为准。
