# Public Workbench

`public workbench` 是面对体验者的网页入口，本地地址是 [http://127.0.0.1:8767](http://127.0.0.1:8767)。

它和私有测试工作台共用 `src/workbench/` 这套内核，但权限更窄。公共模式保留这些能力：选择起点、选择终点、发起任务、看状态、看阶段产物、看最终图片、看自己的历史。目录审阅、收藏、删除、cleanup、inventory 这些系统级能力只留在私有工作台。

本地入口：

```powershell
python run_public_workbench.py
python run_public_workbench.py status
python run_public_workbench.py stop
python run_public_workbench.py restart --no-open-browser
```

公网接入脚本都在 `tools/remote_access/`。

Quick Tunnel：

```powershell
powershell -ExecutionPolicy Bypass -File tools\remote_access\start_public_workbench_quick.ps1
powershell -ExecutionPolicy Bypass -File tools\remote_access\status_public_workbench_quick.ps1
powershell -ExecutionPolicy Bypass -File tools\remote_access\stop_public_workbench_quick.ps1
```

正式 Tunnel：

```powershell
powershell -ExecutionPolicy Bypass -File tools\remote_access\start_public_workbench.ps1
powershell -ExecutionPolicy Bypass -File tools\remote_access\stop_public_workbench.ps1
```

当前模块负责这个应用的公网接入方式。根域名首页、子域名组织、Cloudflare Zone 级配置统一归总仓库下的 `domain-manage/` 管。

能力状态按这几条理解：

- 页面打开后，各项能力按当前环境状态启用
- 文本直跑类入口对 VPN 依赖较低
- 实时采样全链路依赖采样源网络
- 图片终点依赖本机执行服务在线

对体验者而言，`public workbench` 是带能力状态的产品入口。
