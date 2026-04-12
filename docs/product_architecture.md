# 产品架构说明

## 总览

这个项目现在有两块正式产品能力：内容生产链和 QQ 私聊服务。运维面板与内容测试工作台属于开发工具，它们围绕正式产品工作，但不属于正式用户入口。

```text
正式产品
  QQ 私聊服务
  -> 内容生产链

内容生产链
  人物资产 + 实时采样
  -> creative
  -> social_post
  -> prompt_builder
  -> prompt_guard
  -> execution
  -> publish

开发工具
  -> ops dashboard
  -> content workbench + test pipeline
```

## 内容生产链

内容生产链位于 `src/creative/`、`src/social_post/`、`src/prompt_builder/`、`src/prompt_guard/` 和 `src/execution/`。`creative` 负责采样与设计稿生成，`social_post` 负责社媒文案，`prompt_builder` 负责生成标准化 prompt package，`prompt_guard` 负责回调审查与最小修正，`execution` 负责 execution profile、workflow 和 ComfyUI 出图。发布适配位于 `src/publish/`。

## QQ 私聊服务

QQ 服务也是正式产品的一部分，代码位于 `src/publish/`。当前已经拆成接入、消息解释、任务策略、执行回传和运行态存储几个部分，正式控制入口是 [run_qq_bot_service.py](../run_qq_bot_service.py)。用户从 QQ 触发的所有生成请求都先经过这一层，再进入内容生产链。

## 开发工具

开发工具分成运维和测试两类。运维面板在 `src/ops/`，入口是 [run_ops_dashboard.py](../run_ops_dashboard.py)，用于查看 QQ 服务状态、队列、日志和最近 run。内容测试工作台在 `src/studio/`，入口是 [run_content_workbench.py](../run_content_workbench.py)，用于本地发起测试、查看中间产物、复跑和清理。测试编排核心位于 [src/test_pipeline/core.py](../src/test_pipeline/core.py)，工作台与与之重合的批量回放脚本统一复用这一层。

## 共享执行位

QQ 服务和内容测试工作台可以同时在线，但共用同一条本机生成链。共享执行位在 [runtime/service_state/shared/generation_slot.json](../runtime/service_state/shared/generation_slot.json)。谁先占用，谁先进入生成阶段。

## 运行产物

正式 run 和工作台测试 run 都落在 `runtime/runs/<run_id>/`。QQ 服务状态放在 `runtime/service_state/publish/`。运维面板和工作台自己的控制状态与日志放在 `runtime/service_state/sidecars/` 和 `runtime/service_logs/sidecars/`。

## 体验思路

面向用户时，重点是 QQ 触发简单、状态反馈直接、结果回传清楚。面向开发者时，重点是运维面板一眼看清 QQ 服务健康度，内容测试工作台在一个页面内完成测试发起、详情查看、Prompt 差异检查和训练筛选。
