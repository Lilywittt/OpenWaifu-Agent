# domain-manage

`openwaifu-agent.uk` 的根域名入口与域名层配置都在这里维护。

当前目录结构：

- `assets/test.png`：首页背景图源文件
- `assets/test-bg.jpg`：由源图导出的轻量发布图
- `config/cloudflare.mjs`：部署目标配置
- `scripts/build-worker.mjs`：把页面与背景图打包成可部署的单 Worker
- `scripts/deploy-worker.mjs`：通过 Cloudflare API 上传 Worker 并绑定根域名
- `dist/worker.js`：构建产物
- `wrangler.jsonc`：Cloudflare 部署配置

开发与部署：

```bash
npm install
npm run build
npm run dev
npm run check
npm run deploy
```

部署前需要设置 `CLOUDFLARE_API_TOKEN`。

首页背景图来自 `assets/test.png`。
