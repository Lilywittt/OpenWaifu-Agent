# domain-manage

`domain-manage` 管两件事：

- `openwaifu-agent.uk` 根域首页
- `hi.openwaifu-agent.uk` 内容体验工作台公网入口

这里的根域首页是静态 Cloudflare Worker 页面。服务器没开机时，根域首页照样可访问。内容体验工作台是另一条链路：Cloudflare Tunnel 把公网请求接回同级目录 `openwaifu-agent/` 里的 `8767`。

## 首页资源

首页素材现在按用途归档：

- `assets/homepage/source/`
  首页原始来源图。这里只保留人工挑选后仍需要留档的原图。
- `assets/homepage/mobile/`
  移动端首页实际使用的成品图。
- `assets/homepage/backgrounds/`
  桌面端背景拼接实际使用的成品图。这一层是首页背景的唯一事实来源。
- `config/homepage-gallery.mjs`
  首页素材清单。这里只声明首页实际使用的成品图路径和背景焦点。

首页构建和校验脚本都只读取 `assets/homepage/` 下的成品图，不会再从 `openwaifu-agent/runtime/runs/` 之类的运行目录回填或覆盖背景资源。构建时会同时生成：

- `dist/worker.js`
  Cloudflare Worker 入口。这里只保留请求分发和安全响应头，不再内嵌整套图片。
- `dist/index.html`
  本地静态预览页。
- `dist/assets/homepage/`
  首页实际发布到公网域名的静态资源副本，只复制配置里声明的成品图。

## 公网入口

公网入口分成两层：

- 首次接入
  创建或刷新 Cloudflare Tunnel、域名绑定和本地运行配置。
- 日常启动
  读取本地运行配置，启动 `8767` 和 `cloudflared`。

首次接入用 `bootstrap:workbench`。跑通后会生成 `runtime/public_workbench_ingress/runtime.json`。后续日常启动直接读这份文件。

## 关键文件

- `config/cloudflare.mjs`
  Cloudflare 账号、根域、工作台子域名配置。
- `config/homepage-gallery.mjs`
  首页素材清单。
- `scripts/check-homepage-assets.mjs`
  校验首页素材清单和 `assets/homepage/` 下的成品图是否一致。
- `scripts/refresh-homepage-assets.mjs`
  兼容性保护脚本。现在会直接报错，防止旧流程覆盖首页图片。
- `scripts/build-worker.mjs`
  构建根域静态首页 Worker、静态资源目录和本地静态预览页。
- `scripts/deploy-worker.mjs`
  用 Wrangler 发布根域首页 Worker 与静态资源，并确认 custom domain 绑定。
- `scripts/ensure-public-workbench-domain.mjs`
  校正工作台公网域名资源。
- `scripts/get-public-workbench-runtime.mjs`
  读取或刷新本地运行配置。
- `scripts/bootstrap-public-workbench-ingress.ps1`
  串起首次接入所需的完整流程。
- `scripts/start-public-workbench-ingress.ps1`
  启动 `8767` 和 `cloudflared`。
- `scripts/status-public-workbench-ingress.ps1`
  查看工作台公网入口状态。
- `scripts/stop-public-workbench-ingress.ps1`
  停止工作台公网入口。

## 常用命令

```bash
npm.cmd install
npm.cmd run check:homepage-assets
npm.cmd run build
npm.cmd run deploy:homepage
npm.cmd run check:homepage
npm.cmd run bootstrap:workbench
npm.cmd run bootstrap:workbench:refresh
npm.cmd run runtime:workbench
npm.cmd run start:workbench
npm.cmd run status:workbench
npm.cmd run stop:workbench
```

## 首次接入

先准备 `domain-manage/.env.local`：

```env
CLOUDFLARE_API_TOKEN=你的 token
```

然后执行：

```powershell
npm.cmd run bootstrap:workbench
```

这条命令会完成四步：

1. 校正 Cloudflare 侧资源
2. 生成本地运行配置 `runtime/public_workbench_ingress/runtime.json`
3. 启动 `8767`
4. 启动 `cloudflared`

## 日常操作

根域首页更新：

```powershell
npm.cmd run check:homepage-assets
npm.cmd run deploy:homepage
```

内容体验工作台公网入口启动：

```powershell
npm.cmd run start:workbench
npm.cmd run status:workbench
```
