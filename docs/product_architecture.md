# 产品架构说明

## 一句话架构

主产品链负责生产内容；QQ 服务负责用户入口；运维面板和内容测试工作台是两个平级 sidecar。

```text
正式产品链
  人物资产 + 实时采样
  -> creative
  -> social_post
  -> prompt_builder
  -> prompt_guard
  -> execution
  -> publish

本地 sidecar
  -> ops dashboard
  -> content workbench
```

## 谁负责什么

### 1. 生产主链

- `src/creative/`
  - 实时社媒采样
  - 场景设计稿
  - 环境/造型/动作设计稿
- `src/social_post/`
  - 根据人物资产和场景设计稿生成社媒文案
- `src/prompt_builder/`
  - 生成标准化 prompt package
- `src/prompt_guard/`
  - 审核并最小修正最终 Prompt
- `src/execution/`
  - 读取 execution profile 和 workflow，调用 ComfyUI 出图
- `src/publish/`
  - 包装发布输入、适配发布目标

### 2. QQ 私聊服务

QQ 服务现在按职责拆分，不再由一个大脚本承载全部逻辑：

- `src/publish/qq_bot_ingress.py`
  - QQ 网关接入、鉴权、心跳和消息接收
- `src/publish/qq_bot_router.py`
  - 命令归一化、模式识别、消息解释
- `src/publish/qq_bot_task_policy.py`
  - 入队规则、模式规则、忙碌期反馈
- `src/publish/qq_bot_executor.py`
  - 调正式产品链并回传结果
- `src/publish/qq_bot_runtime_store.py`
  - 服务状态、事件流、锁、停机请求
- `src/publish/qq_bot_service.py`
  - 主编排入口

`src/publish/qq_bot_generate_service.py` 只保留兼容 facade，不再是正式入口。

### 3. 运维面板

`src/ops/` 只负责一个 sidecar：本地运维面板。

职责边界：

- 只看 QQ 服务
- 只读结构化状态
- 首页只做运维概览
- 详情页才看内容溯源

它不负责：

- 发起本地内容测试
- 代替 QQ 入口
- 直接改写主链状态

### 4. 内容测试工作台

`src/studio/` 只负责一个 sidecar：本地内容测试工作台。

职责边界：

- 从不同输入起点发起内容测试
- 指定终点停下
- 看中间产物和最终图片
- 复跑最近一次请求
- 删除指定测试 run 目录
- 导出索引和清理报告

它不负责：

- 充当 QQ 用户入口
- 代替运维面板
- 自己维护另一套测试编排真相

### 5. 测试编排核心

`src/test_pipeline/core.py` 是当前唯一测试编排核心。

这里统一定义：

- 合法起点
- 合法终点
- 起点到终点的阶段推进
- 测试摘要和测试元信息

原则是：

- 工作台调用这层
- 与工作台能力重合的批量 runner 也调用这层
- 不允许再出现“工作台一套、runner 一套”的平行编排

## 正式入口和 sidecar 入口

根目录只保留正式入口：

- `run_product.py`
- `run_generate_product.py`
- `run_qq_bot_service.py`
- `run_ops_dashboard.py`
- `run_content_workbench.py`

含义：

- 正式产品链入口和本地控制台入口都在根目录
- `tests/runners/` 不再承担正式服务职责

## 共享执行位

QQ 服务和内容测试工作台可以同时在线，但不能同时占用本机生成链。

共享执行位在：

- `runtime/service_state/shared/generation_slot.json`

规则：

- QQ 和工作台都先申请这个执行位
- 同一时刻只允许一边真正进入生成链
- 另一边收到明确忙碌反馈，而不是静默抢资源

## 运行产物

正式 run 和工作台测试 run 都落在：

- `runtime/runs/<run_id>/`

sidecar 自己的状态和日志不放进 run 目录，而是放在：

- `runtime/service_state/sidecars/`
- `runtime/service_logs/sidecars/`

这样做的原因很直接：

- 正式内容产物继续统一归档
- 运维/工作台自己的状态索引不污染产品 run

## 产品体验思路

### QQ 侧

QQ 侧面对最终用户，重点是：

- 模式清晰
- 触发成本低
- 忙碌反馈直接
- 队列和状态反馈不误导

### 运维面板

运维面板面对维护者，重点是：

- 一眼知道服务是否健康
- 一眼知道当前阶段、队列和最近错误
- 详情页再看 run 溯源

### 内容测试工作台

工作台面对内容调试者，重点是：

- 不必反复去 QQ 发消息
- 不必反复敲 runner 命令
- 左手键盘切换测试，右手只在详情区操作
- 尽量少点击、少滚动、少来回移动鼠标
