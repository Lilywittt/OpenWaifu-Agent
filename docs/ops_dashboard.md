# 运维面板说明

## 定位

运维面板是本地 sidecar，只负责 QQ 服务运维。

它解决的是：

- QQ 服务是否在线
- 当前跑到哪一层
- 队列里还有多少任务
- 最近 run 和最近错误是什么

它不负责：

- 发起本地内容测试
- 替代 QQ 入口
- 管理工作台测试任务

## 启动和控制

```powershell
python run_ops_dashboard.py
python run_ops_dashboard.py status
python run_ops_dashboard.py stop
python run_ops_dashboard.py restart --no-open-browser
python run_ops_dashboard.py --foreground
```

地址：

- [http://127.0.0.1:8765](http://127.0.0.1:8765)

## 首页看什么

首页只放运维概览，不堆内容正文。

包含：

- QQ 服务状态
- 当前阶段
- 当前 runId
- 队列长度
- 最近任务
- 事件流
- stdout / stderr 尾部
- 社媒采样健康
- 最近成功产物和图片预览

## 详情页看什么

详情页才展开内容溯源。

包含：

- 采样原始内容
- 场景设计稿
- 环境设计稿
- 造型设计稿
- 动作设计稿
- 最终用于生图的 Prompt
- Prompt 回调报告
- Prompt 回调前后差异高亮

## 架构

代码在：

- `src/ops/dashboard_service.py`
- `src/ops/dashboard_store.py`
- `src/ops/dashboard_views.py`

设计原则：

- sidecar，不塞进 QQ 主服务
- 只读结构化状态，不承担业务控制逻辑
- 首页看概览，详情页看溯源
- 运维面板只看 QQ run，不混入工作台 run

## 数据来源

运维面板只读这些状态源：

- `runtime/service_state/publish/qq_bot_generate_service/latest_status.json`
- `runtime/service_state/publish/qq_bot_generate_service/service_events.jsonl`
- `runtime/service_state/publish/qq_bot_jobs/jobs.sqlite`
- `runtime/service_logs/publish/qq_bot_generate_service.stdout.log`
- `runtime/service_logs/publish/qq_bot_generate_service.stderr.log`
- `runtime/service_state/social_sampling_health.json`
- `runtime/runs/<run_id>/output/run_summary.json`
- `runtime/runs/<run_id>/prompt_guard/01_review_report.json`
- `runtime/runs/<run_id>/prompt_guard/02_prompt_package.json`

## 标题怎么定

面板标题优先级：

1. `.env` 里的 `QQ_BOT_DISPLAY_NAME`
2. `config/publish/qq_bot_message.json` 里的 `botDisplayName`
3. 项目目录名

## 相关目录

运维面板自己的状态和日志：

- `runtime/service_state/sidecars/ops_dashboard/`
- `runtime/service_logs/sidecars/ops_dashboard/`

QQ 服务状态：

- `runtime/service_state/publish/qq_bot_generate_service/`
- `runtime/service_state/publish/qq_bot_jobs/`

正式 run：

- `runtime/runs/<run_id>/`
