# 目录管理说明

## 顶层结构

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

根目录的 `run_*.py` 分成两类：正式产品入口是 `run_product.py`、`run_generate_product.py` 和 `run_qq_bot_service.py`，开发工具入口是 `run_ops_dashboard.py` 和 `run_content_workbench.py`。

## 正式产品相关目录

`character/` 放人物资产正文，当前主文件是 `character/subject_profile.json`。`config/` 放人物资产入口、LLM 入口、execution profile 入口和发布配置。`prompts/` 放 creative、social_post、prompt_builder 和 prompt_guard 的提示词模板。`src/creative/`、`src/social_post/`、`src/prompt_builder/`、`src/prompt_guard/`、`src/execution/` 和 `src/publish/` 组成正式产品代码。

## 开发工具相关目录

`src/ops/` 是运维面板，`src/studio/` 是内容测试工作台，`src/test_pipeline/` 是测试编排核心。`tests/unit/` 放单元测试，`tests/runners/` 放批量回放和链路验证脚本。与工作台能力重合的批量脚本统一复用 `src/test_pipeline/core.py`。

`tools/qq_bot/` 保留一次性 QQ 调试工具，例如 token、发消息、网关监听和回调接收。

## 运行产物与状态

正式产品链和内容测试工作台都把内容产物放到 `runtime/runs/<run_id>/`。`tests/runners/` 的批量回放仍然保留 `runtime/test_batches/` 作为独立批次区，便于与正式 run 分开看。

QQ 服务状态放在 `runtime/service_state/publish/`。运维面板和工作台自己的状态与日志放在 `runtime/service_state/sidecars/` 和 `runtime/service_logs/sidecars/`。跨入口共享的生成执行位放在 `runtime/service_state/shared/generation_slot.json`。

工作台的运行索引与清理报告统一放在 `runtime/service_state/sidecars/content_workbench/`，其中 `run_index.csv` 用于人工筛选和训练选片，`cleanup_report.*` 用于清理候选审阅。

## 本地临时区

项目根目录可以保留 `.temp/` 作为本机 scratch 区。它不进入正式链路，也不进入正式文档索引。
