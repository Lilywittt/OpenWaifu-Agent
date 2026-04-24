# domain-manage

`domain-manage` 负责 `openwaifu-agent.uk` 根域首页与 `hi.openwaifu-agent.uk` 内容体验工作台入口的 Cloudflare 编排。

同级目录 `openwaifu-agent/` 提供工作台服务本体，这里负责把它接到正式域名，并维护 Tunnel 与 DNS 资源。

核心文件：

- `assets/test.png`：首页背景图源文件
- `assets/test-bg.jpg`：首页发布图
- `config/cloudflare.mjs`：根域首页、工作台子域名、Tunnel 配置
- `scripts/build-worker.mjs`：构建根域首页 Worker
- `scripts/deploy-worker.mjs`：发布根域首页 Worker
- `scripts/ensure-public-workbench-domain.mjs`：确保工作台域名资源齐备
- `scripts/get-public-workbench-runtime.mjs`：拉取 named tunnel 启动信息
- `scripts/start-public-workbench-ingress.ps1`：启动工作台 named tunnel 接入
- `scripts/status-public-workbench-ingress.ps1`：查看工作台入口状态
- `scripts/stop-public-workbench-ingress.ps1`：停止工作台入口

常用命令：

```bash
npm install
npm run check
npm run deploy
npm run start:workbench
npm run status:workbench
npm run stop:workbench
```

运行要求：

- `CLOUDFLARE_API_TOKEN`：用于 `npm run deploy`、`npm run ensure:workbench-domain`、`npm run start:workbench`
- `cloudflared`：用于 `npm run start:workbench`
- 同级目录存在 `openwaifu-agent/`，并且 `python run_public_workbench.py status` 可正常返回
