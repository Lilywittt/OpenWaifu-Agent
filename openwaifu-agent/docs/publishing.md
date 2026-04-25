# 发布服务

发布服务负责把某个 run 的最终图片和社媒文案送到选中的目标。私有测试工作台 `8766` 已经接入这套服务；后续 QQ 触发、定时触发和其他自动化入口也应调用同一组发布接口。

## 当前能力

- 从测试工作台详情区发起发布
- 读取当前 run 的图片和社媒文案
- 每次选择一个发布目标并触发一次动作
- 用浏览器目录选择器把图片和文案另存到本地
- 为每次发布生成 job、artifacts 和 receipts
- 使用 Edge 登录态打开平台页面并准备草稿

当前已经可用的目标：

- `qq_bot_user`
- `local_save_as`
- `pixiv_browser_draft`
- `instagram_browser_draft`

`local_archive` 是内部归档目标，用来把发布包、输入和回执留在项目 runtime 里，方便追踪发布历史。测试工作台前端展示用户可触发目标。

`local_directory` 是脚本和自动化流程使用的服务端目录导出目标。测试工作台里的“本地另存为”对应 `local_save_as`，由浏览器弹出目录选择器，保存成功后回写一条 receipt。

浏览器目标的验收状态：

- `pixiv_browser_draft`：已通过接口烟测，能上传图片并填写标题、说明；默认停在草稿页，由人工确认最终发布。
- `instagram_browser_draft`：已接入独立浏览器会话和 75 秒超时保护；当前页面流程没有稳定填表，失败会返回明确错误。

浏览器发布脚本：

- `run_publish_browser_profile.py status`：查看 Edge 发布配置状态
- `run_publish_browser_profile.py sync-edge`：把当前 Edge 默认登录态同步到受管发布配置
- `run_publish_browser_profile.py cleanup-sessions`：清理发布服务创建的 Edge 会话目录

## 目录

- `src/publish/contracts.py`：发布请求结构
- `src/publish/targets.py`：发布目标读取与解析
- `src/publish/jobs.py`：发布 job 状态
- `src/publish/service.py`：统一发布入口
- `src/publish/pipeline.py`：执行发布计划
- `src/publish/adapter_runner.py`：浏览器平台适配器子进程入口
- `src/publish/adapters/`：目标适配器

## 控制台接口

私有测试工作台通过这组接口调用发布服务：

- `GET /api/publish/targets`
- `POST /api/publish/run`
- `POST /api/publish/client-result`
- `GET /api/publish/jobs/{jobId}`

`POST /api/publish/run` 的请求体：

```json
{
  "runId": "2026-04-24T19-10-12_run",
  "targetId": "qq_bot_user",
  "options": {
    "localExport": {
      "kind": "bundle_folder",
      "name": "Rainy Night 01"
    }
  }
}
```

浏览器平台也走同一个接口：

```json
{
  "runId": "2026-04-24T19-10-12_run",
  "targetId": "pixiv_browser_draft",
  "options": {
    "localExport": {
      "kind": "bundle_folder",
      "name": "Rainy Night 01"
    }
  }
}
```

脚本和自动任务需要导出到服务端目录时，使用 `localDirectory`：

```json
{
  "runId": "2026-04-24T19-10-12_run",
  "localDirectory": "F:/openwaifu-workspace/.local/openwaifu-agent/publish/export-demo",
  "options": {
    "localExport": {
      "kind": "image_only",
      "name": "Rainy Poster"
    }
  }
}
```

浏览器另存为完成后，测试工作台回写结果：

```json
{
  "runId": "2026-04-24T19-10-12_run",
  "targetId": "local_save_as",
  "fileNames": ["Rainy Night 01.png", "Rainy Night 01_social_post.txt"],
  "localExport": {
    "kind": "bundle_folder",
    "name": "Rainy Night 01"
  },
  "containerName": "Rainy Night 01",
  "directoryLabel": "Downloads"
}
```

本地另存协议现在是一套统一结构。`kind` 控制导出图片还是导出图文文件夹，`name` 控制这次导出的命名。浏览器会记住上一次授权的目录；下次再点本地另存，会优先复用这份目录授权，只有你主动更换目录时才重新弹目录选择器。

## 配置

仓库配置放在：

- `config/publish/targets.json`

这里定义系统支持哪些目标、展示名是什么、每个目标走哪个 adapter。

本机配置放在：

- `F:/openwaifu-workspace/.local/openwaifu-agent/publish/targets.local.json`

这里适合放常用目录预设、浏览器认证状态位置、机器私有配置。

Edge 浏览器发布配置默认落在：

- `F:/openwaifu-workspace/.local/openwaifu-agent/publish/browser-auth/edge-user-data`

这份受管配置给发布服务使用。同步命令会把当前 Edge 默认配置里的登录态复制到这里。

浏览器发布运行时会为每次发布创建独立会话目录：

- `F:/openwaifu-workspace/.local/openwaifu-agent/publish/browser-sessions/edge`

独立会话用于隔离 Pixiv、Instagram 等平台页面。登录态同步目录是源，会话目录是每次发布的临时浏览器环境。

## 运行结果

每次发布会写三处结果：

- run 内 artifacts：`runtime/runs/<runId>/publish/service_jobs/<jobId>/`
- job 状态：`runtime/service_state/publish/jobs/<jobId>.json`
- run summary receipts：`runtime/runs/<runId>/output/run_summary.json`

工作台详情区刷新后，会直接显示这次发布的 receipts。

## 使用顺序

首次使用浏览器发布时，先在 Edge 登录 Pixiv、Instagram 等平台，然后关闭 Edge，执行：

```powershell
python run_publish_browser_profile.py sync-edge
```

日常使用前可检查状态：

```powershell
python run_publish_browser_profile.py status
```

发布服务创建的会话目录可定期清理：

```powershell
python run_publish_browser_profile.py cleanup-sessions
```

私有测试工作台的发布面板会显示 Edge 配置状态。登录态缺失、未同步或浏览器目标超时，都会在接口和前端返回明确原因。
