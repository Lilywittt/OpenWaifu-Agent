# ig_roleplay_v3

`ig_roleplay_v3` 是一条单角色内容生产链。正式产品由两部分组成：一条从人物资产和外部采样出发的内容生产链，以及一个 QQ 私聊服务入口。围绕这两部分，项目另外提供了两类开发工具：QQ 运维面板和本地内容测试工作台。

## 首次阅读顺序

第一次接手项目，先看这几份文档：

1. [产品架构说明](./docs/product_architecture.md)
2. [使用说明](./docs/usage.md)
3. [技术思路说明](./docs/technical_strategy.md)
4. [QQ 私聊服务说明](./docs/qq_bot_private_service.md)
5. [运维面板说明](./docs/ops_dashboard.md)
6. [内容测试工作台说明](./docs/content_workbench.md)
7. [目录管理说明](./docs/directory_management.md)

## 正式产品入口

这些脚本都在项目根目录直接运行：

```powershell
python run_product.py
python run_generate_product.py --run-label generate_test
python run_qq_bot_service.py start
```

`run_product.py` 跑完整产品链，`run_generate_product.py` 只跑生成层，`run_qq_bot_service.py` 控制 QQ 私聊服务。

## 开发工具入口

```powershell
python run_ops_dashboard.py
python run_content_workbench.py
```

`run_ops_dashboard.py` 打开 QQ 运维面板，`run_content_workbench.py` 打开本地内容测试工作台。

## 当前主链

```text
QQ 私聊服务
-> 正式产品链

人物资产 + 实时社媒采样
-> creative
-> social_post
-> prompt_builder
-> prompt_guard
-> execution
-> publish
```

QQ 私聊服务负责用户触发、队列、回执和结果回传。运维面板和内容测试工作台都在正式产品之外运行。

## 核心配置入口

人物资产入口在 [config/character_assets.json](./config/character_assets.json)，正文在 [character/subject_profile.json](./character/subject_profile.json)。

LLM 入口在 [config/llm_profiles.json](./config/llm_profiles.json)，具体模型配置在 [config/creative_model.json](./config/creative_model.json) 和 [config/prompt_guard_model.json](./config/prompt_guard_model.json)。

生图基座入口在 [config/execution/active_profile.json](./config/execution/active_profile.json)，当前 profile 在 [config/execution/comfyui_local_animagine_xl.json](./config/execution/comfyui_local_animagine_xl.json)，workflow 模板在 [config/workflows/comfyui/animagine_xl_basic.workflow.json](./config/workflows/comfyui/animagine_xl_basic.workflow.json)。

## 目录抓手

根目录的 `run_*.py` 放正式入口和控制台入口。`src/` 放产品代码和开发工具代码，`tests/runners/` 放批量回放，`tools/qq_bot/` 放一次性 QQ 调试工具，`runtime/` 放运行产物、状态和日志。
