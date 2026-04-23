# QQ 私聊服务说明

## 正式入口

QQ 私聊服务的正式控制入口是 [run_qq_bot_service.py](../run_qq_bot_service.py)：

```powershell
python run_qq_bot_service.py start
python run_qq_bot_service.py status
python run_qq_bot_service.py stop
python run_qq_bot_service.py restart
python run_qq_bot_service.py foreground
```

`start / status / stop / restart` 用于正式运维，`foreground` 适合本机调试。

## 服务结构

QQ 服务代码位于 `src/publish/`。`qq_bot_ingress.py` 负责网关接入、鉴权、心跳和消息接收，`qq_bot_router.py` 负责命令归一化和消息解释，`qq_bot_task_policy.py` 负责入队与模式策略，`qq_bot_executor.py` 调正式产品链并回传结果，`qq_bot_runtime_store.py` 管服务状态、事件流和停机请求，`qq_bot_service.py` 作为主编排入口。[src/publish/qq_bot_generate_service.py](../src/publish/qq_bot_generate_service.py) 目前保留兼容壳。

## 当前交互能力

体验者模式常用指令是 `生成`、`状态`、`帮助`、`/g`、`/s`、`/h`。开发者模式常用指令是 `开发者模式`、`体验者模式`、`注入场景稿`、`/d`、`/e`、`/i`，并支持发送场景稿正文或场景稿 JSON。

## 并发和队列

QQ 服务采用“并发接单，串行生产”。多用户可以同时发消息，真正的生成任务同一时刻只跑一条，队列持久化保存在本地。同一用户在当前任务运行或排队期间不会重复入队，需要等当前任务结束后再提交下一轮。

## 与工作台的关系

QQ 服务和内容测试工作台可以同时在线，但共享一个本地生成执行位：`runtime/service_state/shared/generation_slot.json`。谁先占用，谁先进入生成阶段。

## 用户体验思路

体验者模式追求触发成本低、指令清晰、忙碌反馈直接。开发者模式追求场景稿注入路径清楚、模式切换明确、文本输入无需手工拼完整 JSON。

## 运行态文件

服务状态位于 `runtime/service_state/publish/qq_bot_generate_service/latest_status.json` 和 `service_events.jsonl`，队列位于 `runtime/service_state/publish/qq_bot_jobs/jobs.sqlite`，开发者场景稿缓存位于 `runtime/service_state/publish/qq_bot_scene_drafts/<user>/latest.json`，日志位于 `runtime/service_logs/publish/qq_bot_generate_service.stdout.log` 与 `stderr.log`。
