# 目录管理说明

## 顶层目录

```text
character/
config/
docs/
prompts/
runtime/
src/
tests/
tools/
run_product.py
run_generate_product.py
run_qq_bot_service.py
run_ops_dashboard.py
run_content_workbench.py
```

顶层规则：

- 根目录 `run_*.py` 只放正式入口和本地控制台入口
- `src/` 只放产品代码
- `tests/` 只放测试代码和批量回放入口
- `tools/` 只放一次性调试工具
- `runtime/` 只放运行产物、状态和日志

## 配置层

```text
config/
  character_assets.json
  llm_profiles.json
  creative_model.json
  prompt_guard_model.json
  execution/
    active_profile.json
    comfyui_local_animagine_xl.json
  workflows/
    comfyui/
      animagine_xl_basic.workflow.json
  publish/
    qq_bot_message.json
```

规则：

- `config/*.json` 优先放“当前启用哪份配置”的入口
- 人物资产正文、Prompt 模板、workflow 模板不要塞进 `.env`
- execution profile 和 workflow 模板分开维护

## 内容层

```text
character/
  subject_profile.json

prompts/
  creative/
  social_post/
  prompt_builder/
  prompt_guard/
```

规则：

- `character/` 放人物资产正文
- `prompts/` 放提示词模板
- `.env` 只做环境覆盖，不承载内容本体

## 源码层

```text
src/
  creative/
  social_post/
  prompt_builder/
  prompt_guard/
  execution/
  publish/
  ops/
  studio/
  test_pipeline/
```

职责边界：

- `src/ops/`
  - 运维面板
- `src/studio/`
  - 内容测试工作台
- `src/test_pipeline/`
  - 测试编排唯一真相

这三层要分开：

- `ops` 看系统
- `studio` 做本地内容测试
- `test_pipeline` 定义测试规则

## 测试层

```text
tests/
  runners/
  unit/
```

规则：

- `tests/runners/` 只放批量回放和链路验证入口
- `tests/unit/` 只放单元测试
- 与工作台能力重合的 batch runner 必须复用 `src/test_pipeline/core.py`

## QQ 调试工具

```text
tools/
  qq_bot/
```

规则：

- 这里只放 token、发消息、网关监听、回调接收之类的一次性调试工具
- 不参与正式服务入口

## 正式 run 产物

```text
runtime/
  runs/
    <run_id>/
```

正式产品链和内容测试工作台都把内容产物放进 `runtime/runs/`。

## 批量测试产物

```text
runtime/
  test_batches/
    <batch_kind>/
```

`tests/runners/` 的批量回放仍然保留独立批次目录，不和正式 run 混在一起。

## QQ 服务状态

```text
runtime/
  service_state/
    publish/
      qq_bot_generate_service/
      qq_bot_jobs/
      qq_bot_private_state/
      qq_bot_scene_drafts/
```

## sidecar 状态和日志

```text
runtime/
  service_state/
    sidecars/
      content_workbench/
      ops_dashboard/
    shared/
      generation_slot.json

runtime/
  service_logs/
    publish/
    sidecars/
```

规则：

- 运维面板和工作台自己的控制状态放 `service_state/sidecars/`
- QQ 服务状态放 `service_state/publish/`
- 跨入口共享执行位放 `service_state/shared/`

## 工作台索引和清理报告

内容测试工作台的索引统一放在：

```text
runtime/service_state/sidecars/content_workbench/
```

关键文件：

- `latest_status.json`
- `history.jsonl`
- `last_request.json`
- `run_index.jsonl`
- `run_index.csv`
- `cleanup_report.json`
- `cleanup_report.csv`

说明：

- `run_index.csv` 适合人工筛选和后续训练选片
- `cleanup_report.*` 只给删除候选，不直接删文件

## 本地临时目录

项目根目录允许保留本地 `.temp/` 作为手动 scratch 区，但它不是正式产品目录，也不参与正式链路和文档索引。
