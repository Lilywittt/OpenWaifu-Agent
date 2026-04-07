# 产品使用说明

## 运行前提

需要满足两类前提：

1. LLM 可用
2. ComfyUI 可用

具体环境变量和本地资源见 [环境配置说明](./environment_setup.md)。

## 最常用命令

### 1. 直接运行一次完整链路

```powershell
python run_product.py
```

这会默认执行一次 `single`：

- 采样
- creative
- social_post
- prompt_builder
- execution
- 出图

### 2. 带标签运行一次

```powershell
python run_product.py single --run-label my_test
```

### 3. 查看最新一次运行结果

```powershell
python run_product.py review
```

### 4. 查看 runtime 路径

```powershell
python run_product.py paths
```

### 5. 从已有设计稿直接跑中下游

如果已经有 `creative/05_creative_package.json`，可以直接跳过 creative 层，只跑 `prompt_builder + execution`：

```powershell
python tests/runners/prompt_execution_runner.py --source F:\path\to\runtime\runs\<run_id>
```

`--source` 支持三种输入：

- 一个完整 run 目录
- 一个 `creative/` 目录
- 一个 `05_creative_package.json` 文件

如果要从一个批次里连续取多个样本，可以用：

```powershell
python tests/runners/prompt_execution_runner.py --source-batch F:\path\to\batch --count 3 --label replay
```

### 6. 从已有设计稿直接回放社媒文案

如果只想测试 `social_post`，可以直接吃已有 `creative` 产物：

```powershell
python tests/runners/social_post_runner.py --count 3 --label social_review
```

不传 `--source` 时，会默认取最近几次正式 run 的 `creative/05_creative_package.json`。

也可以显式指定来源：

```powershell
python tests/runners/social_post_runner.py --source F:\path\to\runtime\runs\<run_id> --count 1
```

或者从一个批次里连续取多个样本：

```powershell
python tests/runners/social_post_runner.py --source-batch F:\path\to\batch --count 3 --label social_review
```

### 7. 只运行生成层产品链路

如果要恢复旧的“只跑生成层，不进入发布层”入口，可以用：

```powershell
python tests/runners/run_generate_product.py --run-label generate_test
```

### 8. 运行全部单元测试

```powershell
python -m unittest discover -s tests/unit -v
```

## 成功运行后会得到什么

一次成功运行后，会生成：

- creative 产物
- social post 产物
- prompt builder 产物
- execution 产物
- 最终图片
- `output/social_post.txt`
- `output/run_summary.json`

所有正式产物都落在：

`runtime/runs/<run_id>/`

## 推荐排查顺序

如果结果不对，建议按这个顺序排查：

1. 先看 `creative/01_world_design.json`
2. 再看三份设计稿
3. 再看 `prompt_builder/00_image_prompt.json`
4. 最后看 `execution/01_workflow_request.json`

这样可以区分问题是在：

- 创意层
- prompt 编译层
- 执行层

## 当前验收标准

当前基础验收标准是：

- 可以稳定从采样跑到出图
- 运行目录结构稳定
- prompt 可以稳定注入 ComfyUI workflow

内容质量本身还需要持续迭代，尤其是 prompt_builder 对冲突约束的处理。
