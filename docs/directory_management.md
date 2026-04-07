# 目录结构管理说明

## 目标

目录管理的目标只有两个：

1. 当前有效结构一眼能看清
2. 不让历史遗留在主链路里继续堆积

## 当前源码分层

```text
src/
  creative/
  prompt_builder/
  execution/
```

辅助基础模块保留在 `src/` 根下：

- `character_assets.py`
- `env.py`
- `io_utils.py`
- `llm.py`
- `llm_schema.py`
- `prompt_loader.py`
- `runtime_layout.py`

## 当前 prompt 分层

```text
prompts/
  creative/
  prompt_builder/
```

## 当前配置分层

```text
config/
  creative_model.json
  execution/
  workflows/comfyui/
```

## Runtime 管理规则

正式运行产物只允许进入：

```text
runtime/
  runs/
    <run_id>/
      input/
      creative/
      prompt_builder/
      execution/
      output/
      trace/
```

说明：

- `input/`：输入快照
- `creative/`：creative 层产物
- `prompt_builder/`：prompt 编译产物
- `execution/`：workflow 注入与执行记录
- `output/`：最终图片与运行摘要
- `trace/`：LLM request/response trace

## 目录管理原则

### 1. 不保留半迁移目录

如果某一层退出现行架构，就不应再保留与之并行的旧目录。

### 2. 不在 runtime 里堆临时垃圾

正式运行只写 `runtime/runs/`。  
测试批次和服务状态分别单独管理，不混进正式产物目录。

### 3. 不提交缓存

`__pycache__`、运行缓存、临时输出不进入源码树。

### 4. 目录名反映职责，不反映历史

目录应该描述当前职责，比如：

- `prompt_builder`
- `execution`

而不是继续沿用已经失效的旧名。
