# 架构说明

## 当前有效架构

```text
人物原始资产 ----------\
                        -> 场景设计稿 -> 环境、布景与光影设计
外部发散变量采样层 ----/               -> 服装与造型设计
                                        -> 动作与姿态、神态设计

人物原始资产 + 三份设计 ---------------------------------> 生图Prompt(JSON: positive / negative)

生图Prompt + 执行配置 + ComfyUI workflow -----------------> 生成图像
```

## 分层职责

### 1. Creative

`src/creative/` 负责：

- 外部采样 shortlist
- 采样过滤
- 场景设计稿
- 环境、布景与光影设计
- 服装与造型设计
- 动作与姿态、神态设计

这里是当前产品里真正的创意层。

### 2. Prompt Builder

`src/prompt_builder/` 负责：

- 读取原始人物资产
- 读取三份设计稿
- 产出给生图模型使用的 prompt JSON

它当前输出协议固定为：

```json
{
  "positive": "",
  "negative": ""
}
```

系统内再统一整理成：

```json
{
  "meta": {
    "createdAt": "",
    "runMode": "default"
  },
  "defaultRunContext": {},
  "positivePrompt": "",
  "negativePrompt": ""
}
```

### 3. Execution

`src/execution/` 负责：

1. 读取 `positivePrompt / negativePrompt`
2. 读取 execution profile 和 ComfyUI workflow 模板
3. 把 prompt、checkpoint、尺寸、采样参数确定性注入 workflow
4. 提交 ComfyUI 并下载最终图片

这层不负责再做创意。

## 上下游关系

- `人物原始资产` 和 `外部发散变量采样层` 是并行上游，一起汇入 `场景设计稿`
- `场景设计稿` 之后是三条同层分支：
  - `环境、布景与光影设计`
  - `服装与造型设计`
  - `动作与姿态、神态设计`
- `prompt_builder` 接收原始人物资产和三份设计稿
- `execution` 接收 prompt package

## Prompt Builder 输入顺序

传给 LLM 的 `imagePromptInput` 内部顺序固定为：

1. `subjectProfile`
2. `actionDesign`
3. `stylingDesign`
4. `environmentDesign`

也就是：

1. 原始人物资产
2. 动作与姿态、神态设计稿
3. 服装与造型设计稿
4. 环境、布景与光影设计稿

## 执行基座

当前执行层固定使用：

- shared checkpoint: `animagine-xl-4.0-opt.safetensors`
- execution profile: `config/execution/comfyui_local_animagine_xl.json`
- workflow template: `config/workflows/comfyui/animagine_xl_basic.workflow.json`

## 当前不再采用的旧架构

以下内容已经退出现行架构，不再作为产品正确结构的一部分：

- 旧 `render` 目录
- 旧 `prompt_compiler`
- 旧 `render_director`
- 单独镜头模块

镜头与构图已经并入 `环境、布景与光影设计`。
