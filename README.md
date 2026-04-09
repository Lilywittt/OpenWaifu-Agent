# ig_roleplay_v3

`ig_roleplay_v3` 当前是一个已经打通的单角色内容生产链路：

```text
人物原始资产 + 外部发散变量采样层
-> 场景设计稿
   -> 社媒文案
   -> 环境、布景与光影设计 + 服装与造型设计 + 动作与姿态、神态设计
      -> 生图Prompt(JSON: positive / negative)
      -> ComfyUI workflow
      -> 生成图像
```

镜头与构图内容已经并入 `环境、布景与光影设计`，不再保留单独镜头模块。

## 项目亮点

- 单角色内容生产链已经打通：`creative -> social_post -> prompt_builder -> execution -> publish`
- 生图执行层走本地 ComfyUI，固定基座为 `animagine-xl-4.0-opt.safetensors`
- QQ 私聊产品链已经可用，支持体验者模式和开发者模式两种文本交互

## 当前真实可用能力

- 完整产品链运行：从创意到生图，再到 QQ 私聊发布
- 生成层独立运行：只跑 `creative -> social_post -> prompt_builder -> execution`
- QQ 私聊体验者模式：`生成 / 状态 / 帮助`
- QQ 私聊开发者模式：注入场景稿后直跑到出图

当前不作为可用能力承诺的内容：
- QQ 按钮交互
- QQ 自定义 keyboard

## 第一次看项目建议

如果你是第一次点进来，建议按这个顺序看：

1. [架构说明](./docs/product_architecture.md)
2. [产品使用说明](./docs/usage.md)
3. [QQ 私聊服务说明](./docs/qq_bot_private_service.md)

## 文档索引

- [技术思路说明](./docs/technical_strategy.md)
- [架构说明](./docs/product_architecture.md)
- [产品使用说明](./docs/usage.md)
- [QQ 私聊服务说明](./docs/qq_bot_private_service.md)
- [目录结构管理说明](./docs/directory_management.md)
- [环境配置说明](./docs/environment_setup.md)

## 常用入口

完整产品链：

```powershell
python run_product.py
```

QQ 私聊服务：

```powershell
python tests/runners/qq_bot_generate_service_ctl.py start
```

如果你只想快速确认项目当前最核心的两条入口，这两条就够：

- `python run_product.py`
- `python tests/runners/qq_bot_generate_service_ctl.py start`

## 当前目录分层

- `src/creative/`
- `src/social_post/`
- `src/prompt_builder/`
- `src/execution/`
- `prompts/creative/`
- `prompts/social_post/`
- `prompts/prompt_builder/`
- `src/publish/`
- `config/publish/`
- `config/execution/`
- `config/workflows/comfyui/`

## 当前执行基座

- shared checkpoint: `animagine-xl-4.0-opt.safetensors`
- execution profile: `config/execution/comfyui_local_animagine_xl.json`
- workflow template: `config/workflows/comfyui/animagine_xl_basic.workflow.json`
