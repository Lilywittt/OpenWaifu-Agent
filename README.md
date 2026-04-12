# ig_roleplay_v3

`ig_roleplay_v3` 是一条单角色内容生产链：从人物资产和外部采样出发，生成场景设计稿、三份衍生设计稿、社媒文案、最终生图 Prompt，并通过 ComfyUI 出图。

## 先看什么

第一次接手项目，按这个顺序看：

1. [产品架构说明](./docs/product_architecture.md)
2. [使用说明](./docs/usage.md)
3. [QQ 私聊服务说明](./docs/qq_bot_private_service.md)
4. [运维面板说明](./docs/ops_dashboard.md)
5. [内容测试工作台说明](./docs/content_workbench.md)
6. [目录管理说明](./docs/directory_management.md)

## 正式入口

这些脚本都在项目根目录直接运行：

```powershell
python run_product.py
python run_generate_product.py --run-label generate_test
python run_qq_bot_service.py start
python run_ops_dashboard.py
python run_content_workbench.py
```

对应职责：

- `run_product.py`：完整产品链路
- `run_generate_product.py`：只跑生成层，不经过发布层
- `run_qq_bot_service.py`：QQ 私聊服务控制入口
- `run_ops_dashboard.py`：本地运维面板，只看 QQ 服务
- `run_content_workbench.py`：本地内容测试工作台，不走 QQ

## 入口关系

这套系统分成三类入口：

- 正式入口
  - `run_product.py`
  - `run_generate_product.py`
  - `run_qq_bot_service.py`
- 本地 sidecar
  - `run_ops_dashboard.py`
  - `run_content_workbench.py`
- 批量测试/回放
  - `tests/runners/`

原则很简单：

- 根目录 `run_*.py` 只放正式入口和本地控制台入口
- `tests/runners/` 只放批量回放和链路验证，不承担正式服务职责
- `tools/qq_bot/` 只放一次性 QQ 协议调试工具

## 当前有效链路

```text
人物原始资产 + 实时社媒采样
-> 场景设计稿
-> 环境设计稿
-> 造型设计稿
-> 动作设计稿
-> 社媒文案
-> Prompt Builder
-> Prompt Guard
-> ComfyUI 执行
-> 图片产物
-> 发布层
```

## 核心配置入口

人物资产：

- [config/character_assets.json](./config/character_assets.json)
- [character/subject_profile.json](./character/subject_profile.json)

LLM 配置：

- [config/llm_profiles.json](./config/llm_profiles.json)
- [config/creative_model.json](./config/creative_model.json)
- [config/prompt_guard_model.json](./config/prompt_guard_model.json)

生图基座：

- [config/execution/active_profile.json](./config/execution/active_profile.json)
- [config/execution/comfyui_local_animagine_xl.json](./config/execution/comfyui_local_animagine_xl.json)
- [config/workflows/comfyui/animagine_xl_basic.workflow.json](./config/workflows/comfyui/animagine_xl_basic.workflow.json)

## 当前运维/测试控制台的定位

- 运维面板：只对 QQ 服务负责，解决“服务是否在线、当前跑到哪、队列和最近 run 怎样”的问题
- 内容测试工作台：只对本地内容测试负责，解决“从不同起点跑到不同终点、看中间产物、复跑和筛选”的问题

两者都是 sidecar，不进入正式产品主链。
