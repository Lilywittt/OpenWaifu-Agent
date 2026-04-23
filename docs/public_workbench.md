# Public Workbench 说明

`public workbench` 是面对体验者的网页入口，本机地址是 [http://127.0.0.1:8767](http://127.0.0.1:8767)。它和私有工作台共用同一个 `src/workbench/` 内核，但权限边界更窄。

公共模式保留这些能力：选择起点、选择终点、发起任务、查看状态、查看阶段产物、查看最终图片、查看自己的历史。文字型起点对外开放，本地文件型起点继续只留在私有工作台。删目录、收藏、审阅任意本地路径、cleanup、inventory、全局历史这些系统级能力都不对外开放。

公共模式的历史和详情按 `ownerId` 隔离。当前 Quick Tunnel 没有 `Access` 登录门禁，所以这层隔离依赖当前会话身份；以后切正式 `Cloudflare Tunnel + Access`，`ownerId` 会直接绑定 `Access` 身份。

## 本机入口

```powershell
python run_public_workbench.py
python run_public_workbench.py status
python run_public_workbench.py stop
python run_public_workbench.py restart --no-open-browser
```

## 公网接入

公网接入脚本统一放在 [F:\openclaw-dev\workspace\projects\ig_roleplay_v3\tools\remote_access](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/tools/remote_access)。当前有两套方式。

### Quick Tunnel

这是当前最快跑通公网的方式，不需要域名。

```powershell
powershell -ExecutionPolicy Bypass -File tools\remote_access\start_public_workbench_quick.ps1
powershell -ExecutionPolicy Bypass -File tools\remote_access\status_public_workbench_quick.ps1
powershell -ExecutionPolicy Bypass -File tools\remote_access\stop_public_workbench_quick.ps1
```

这三条命令就是公网 Quick Tunnel 的完整入口：

- `start_public_workbench_quick.ps1`：启动 `8767` 的 public workbench，并直接打印当前公网地址
- `status_public_workbench_quick.ps1`：打印当前公网地址、健康状态、PID、状态文件和日志位置
- `stop_public_workbench_quick.ps1`：停止当前公网入口

启动后会生成一个随机的 `https://*.trycloudflare.com` 地址。当前地址和运行状态固定写到：

- [F:\openclaw-dev\workspace\projects\ig_roleplay_v3\runtime\service_state\shared\remote_access\cloudflared_public_workbench_quick.json](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/runtime/service_state/shared/remote_access/cloudflared_public_workbench_quick.json)
- [F:\openclaw-dev\workspace\projects\ig_roleplay_v3\runtime\service_logs\remote_access\cloudflared.public_workbench.quick.stdout.log](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/runtime/service_logs/remote_access/cloudflared.public_workbench.quick.stdout.log)
- [F:\openclaw-dev\workspace\projects\ig_roleplay_v3\runtime\service_logs\remote_access\cloudflared.public_workbench.quick.stderr.log](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/runtime/service_logs/remote_access/cloudflared.public_workbench.quick.stderr.log)

Quick Tunnel 适合快速分享和验证。它没有正式登录门禁，地址也是临时的。

当前这台机器上，Quick Tunnel 的脚本固定使用 `http2`。脚本里已经做了健康检查，公网地址是否可用以 `status_public_workbench_quick.ps1` 的输出为准，不要只看进程是否还活着。

### 正式 Tunnel + Access

如果以后有域名，就继续用这三份模板和脚本：

- [F:\openclaw-dev\workspace\projects\ig_roleplay_v3\tools\remote_access\cloudflared.public_workbench.example.yml](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/tools/remote_access/cloudflared.public_workbench.example.yml)
- [F:\openclaw-dev\workspace\projects\ig_roleplay_v3\tools\remote_access\start_public_workbench.ps1](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/tools/remote_access/start_public_workbench.ps1)
- [F:\openclaw-dev\workspace\projects\ig_roleplay_v3\tools\remote_access\stop_public_workbench.ps1](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/tools/remote_access/stop_public_workbench.ps1)

## 能力边界

`public workbench` 页面本身能否打开，和页面里的每一项能力能否使用，不是同一件事。

`场景稿文本 / JSON` 这类直跑链路，对 VPN 依赖较低。`实时采样全链路` 依赖外部采样源，可用性明显受网络环境影响。生图终点还依赖你本机执行服务是否在线。

所以对体验者来说，`public workbench` 是一个带能力状态的产品入口。公网打通，只代表页面可访问；并不代表实时采样和生图终点在任何时刻都一定可用。
