# 目录结构管理说明

## 源码分层

```text
src/
  creative/
  social_post/
  prompt_builder/
  execution/
  publish/
```

基础设施模块保留在 `src/` 根下，例如：

- `character_assets.py`
- `env.py`
- `io_utils.py`
- `llm.py`
- `prompt_loader.py`
- `runtime_layout.py`
- `product_pipeline.py`

## 正式运行目录

```text
runtime/
  runs/
    <run_id>/
      input/
      creative/
      social_post/
      prompt_builder/
      execution/
      publish/
      output/
      trace/
```

规则：

- `runtime/runs/` 只放正式运行产物。
- `runtime/test_batches/` 只放测试批次。
- `output/` 只放最终结果和摘要。
- `trace/` 只放 LLM 请求与响应。

## QQ 私聊附加目录

```text
runtime/
  service_state/
    publish/
      qq_bot_generate_service/
      qq_bot_private_state/
  service_logs/
    publish/
      qq_bot_generate_service.stdout.log
      qq_bot_generate_service.stderr.log
```

开发者模式的场景稿缓存单独归到运行时服务状态里：

```text
runtime/
  service_state/
    publish/
      qq_bot_scene_drafts/
        <user>/
          latest.json
          history/
            <timestamp>.json
```

用途：

- `qq_bot_scene_drafts/` 只存开发者模式下最近一次场景稿和历史注入记录
- 它属于运行时服务状态，不属于正式 run 产物
- 正式 run 仍只落在 `runtime/runs/`
- `latest.json` 始终覆盖最近一次注入，`history/` 追加历史并按每用户最近 `20` 份自动清理
- `service_logs/publish/` 只放后台服务 stdout/stderr，不放正式产物

## 测试脚本目录

```text
tests/
  runners/
  unit/
```

规则：

- `tests/runners/` 只放可直接执行的 runner
- `tests/unit/` 只放 `test_*.py`
- 生产逻辑不直接调用 `tests/runners/`

这也是为什么“从场景稿直跑到生图”的正式实现已经抽回到 `src/product_pipeline.py`，runner 只是壳。
