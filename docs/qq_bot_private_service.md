# QQ 私聊服务说明

## 正式入口

QQ 私聊服务只认这一套控制命令：

```powershell
python run_qq_bot_service.py start
python run_qq_bot_service.py status
python run_qq_bot_service.py stop
python run_qq_bot_service.py restart
python run_qq_bot_service.py foreground
```

说明：

- `start / status / stop / restart` 是正式运维命令
- `foreground` 只用于本机调试
- `tests/runners/` 不再放正式 QQ 服务控制脚本

## 服务内部拆分

QQ 服务现在按职责拆开：

- `src/publish/qq_bot_ingress.py`
  - QQ 网关接入、鉴权、心跳和消息接收
- `src/publish/qq_bot_router.py`
  - 命令归一化、模式识别和消息解释
- `src/publish/qq_bot_task_policy.py`
  - 入队规则、模式规则、忙碌期反馈
- `src/publish/qq_bot_executor.py`
  - 调正式产品链并回传结果
- `src/publish/qq_bot_runtime_store.py`
  - 服务状态、事件流、锁和停机请求
- `src/publish/qq_bot_service.py`
  - 主编排入口

`src/publish/qq_bot_generate_service.py` 只保留兼容 facade。

## 当前交互能力

体验者模式：

- `生成`
- `状态`
- `帮助`
- `/g`
- `/s`
- `/h`

开发者模式：

- `开发者模式`
- `体验者模式`
- `注入场景稿`
- `/d`
- `/e`
- `/i`

开发者模式下支持：

- 发送场景稿正文
- 发送场景稿 JSON

## 并发和队列规则

QQ 服务是“并发接单，串行生产”。

含义：

- 多个用户可以同时发消息
- 真正的生成任务同一时刻只跑一条
- 队列持久化保存在本地

同一用户规则更严格：

- 只要当前用户已经有任务在运行或排队，就不能再提交新任务
- 必须等当前任务完成、失败返回或被中断后，才能再次入队

## 和工作台的关系

QQ 服务和内容测试工作台可以同时在线，但共享一个本地生成执行位：

- `runtime/service_state/shared/generation_slot.json`

规则：

- QQ 服务和工作台都先申请执行位
- 谁先占用，另一边就被明确拒绝
- 不允许静默抢机器

## 用户端体验原则

体验者模式重点是：

- 触发成本低
- 指令清晰
- 忙碌反馈明确
- 不误导用户是否真的已入队

开发者模式重点是：

- 场景稿注入路径清楚
- 文本输入不要求用户自己拼完整 JSON
- 模式切换有明确引导

## 运行态文件

服务状态：

- `runtime/service_state/publish/qq_bot_generate_service/latest_status.json`
- `runtime/service_state/publish/qq_bot_generate_service/service_events.jsonl`

队列：

- `runtime/service_state/publish/qq_bot_jobs/jobs.sqlite`

开发者场景稿缓存：

- `runtime/service_state/publish/qq_bot_scene_drafts/<user>/latest.json`

日志：

- `runtime/service_logs/publish/qq_bot_generate_service.stdout.log`
- `runtime/service_logs/publish/qq_bot_generate_service.stderr.log`
