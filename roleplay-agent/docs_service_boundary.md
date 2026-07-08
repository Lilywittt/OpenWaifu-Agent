# Service Boundary

## 模块边界

Roleplay Agent 的核心服务负责角色扮演聊天、上下文组装、对话记忆、配置界面和发布出口。QQ 是发布出口之一，当前实现使用同一个 QQ 账号承载角色聊天和系统指令触发的生图流程。

OpenWaifu Agent 的生图能力通过 `image_bridge` 调用。Roleplay Agent 读取桥接配置、管理聊天状态和指令状态，生图执行由已有 OpenWaifu Agent 服务能力完成。

## 运行状态

运行状态集中放在 `runtime/`：

```text
runtime/conversations/        用户多轮对话
runtime/memory/               用户记忆
runtime/service_logs/         QQ 发布出口日志
runtime/service_state/        服务锁、状态和事件
runtime/users/                用户路由状态
runtime/qq_gateway/           QQ 网关事件和身份记录
runtime/llm_traces/           可选模型调用追踪
```

这些文件属于本机运行数据，已从 Git 提交中排除。

## 配置边界

密钥统一从 `.env` 读取。模型配置只保存 env 名称、base URL、模型名和采样参数。QQ 配置只保存 env 名称与运行参数。

## 进程边界

QQ 发布出口使用 `runtime/service_state/qq_publish_outlet/service.lock.json` 记录进程锁，启动前会清理陈旧锁并检查当前服务状态。停止命令写入 stop request，服务循环自行收束连接并释放状态。
