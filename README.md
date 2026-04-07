# ig_roleplay_v3

`ig_roleplay_v3` 当前是一个已经打通的单角色内容生产链路：

```text
人物原始资产 + 外部发散变量采样层
-> 场景设计稿
-> 环境、布景与光影设计 + 服装与造型设计 + 动作与姿态、神态设计
-> 生图Prompt(JSON: positive / negative)
-> ComfyUI workflow
-> 生成图像
```

镜头与构图内容已经并入 `环境、布景与光影设计`，不再保留单独镜头模块。

## 文档索引

- [技术思路说明](./docs/technical_strategy.md)
- [架构说明](./docs/product_architecture.md)
- [产品使用说明](./docs/usage.md)
- [目录结构管理说明](./docs/directory_management.md)
- [环境配置说明](./docs/environment_setup.md)

## 当前目录分层

- `src/creative/`
- `src/prompt_builder/`
- `src/execution/`
- `prompts/creative/`
- `prompts/prompt_builder/`
- `config/execution/`
- `config/workflows/comfyui/`

## 当前执行基座

- shared checkpoint: `animagine-xl-4.0-opt.safetensors`
- execution profile: `config/execution/comfyui_local_animagine_xl.json`
- workflow template: `config/workflows/comfyui/animagine_xl_basic.workflow.json`
