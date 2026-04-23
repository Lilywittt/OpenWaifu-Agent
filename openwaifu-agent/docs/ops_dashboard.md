# 运维面板说明

## 定位

运维面板是本地 QQ 服务控制台，地址是 [http://127.0.0.1:8765](http://127.0.0.1:8765)。它把 QQ 服务状态、当前阶段、队列、事件流、日志尾部和最近 run 的内容溯源放在一个页面里，方便维护者快速判断服务是否健康、问题卡在哪一层、最近一次 run 的内容是怎样形成的。

## 启动和控制

```powershell
python run_ops_dashboard.py
python run_ops_dashboard.py status
python run_ops_dashboard.py stop
python run_ops_dashboard.py restart --no-open-browser
python run_ops_dashboard.py --foreground
```

## 页面结构

首页聚焦运维概览，包含 QQ 服务状态、当前阶段、当前 runId、队列长度、最近任务、事件流、stdout/stderr 尾部、社媒采样健康，以及最近成功产物的预览。详情页聚焦 run 溯源，展示采样原始内容、场景设计稿、环境设计稿、造型设计稿、动作设计稿、最终用于生图的 Prompt、Prompt 回调报告，以及回调前后差异高亮。

## 代码结构

`src/ops/dashboard_service.py` 提供本地 HTTP 服务和 API，`src/ops/dashboard_store.py` 聚合 QQ 服务状态、日志和最近 run 信息，`src/ops/dashboard_views.py` 渲染首页和详情页。详情页内容由共享的 [src/run_detail_store.py](../src/run_detail_store.py) 组织，因此工作台和运维面板看到的是同一套 run 详情数据。

## 数据来源

运维面板读取的核心状态源包括 `runtime/service_state/publish/qq_bot_generate_service/latest_status.json`、`service_events.jsonl`、`runtime/service_state/publish/qq_bot_jobs/jobs.sqlite`、QQ 服务 stdout/stderr 日志、`runtime/service_state/social_sampling_health.json`，以及 `runtime/runs/<run_id>/` 下的 `run_summary.json`、Prompt 回调报告和回调后 prompt package。

## 标题和目录

面板标题优先读取 `.env` 里的 `QQ_BOT_DISPLAY_NAME`，其次读取 `config/publish/qq_bot_message.json` 里的 `botDisplayName`，最后回退到项目目录名。

运维面板自己的状态和日志在 `runtime/service_state/sidecars/ops_dashboard/` 与 `runtime/service_logs/sidecars/ops_dashboard/`。QQ 服务运行态继续放在 `runtime/service_state/publish/qq_bot_generate_service/` 和 `runtime/service_state/publish/qq_bot_jobs/`。被面板展示的正式 run 仍然统一放在 `runtime/runs/<run_id>/`。
