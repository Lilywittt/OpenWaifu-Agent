# ig_roleplay_v3

`ig_roleplay_v3` 现在有两层能力：一层是内容生产核心，另一层是围绕它的入口。公共入口有 `QQ` 和 `public workbench`；私有工具有 `运维面板` 和 `内容测试工作台`。`public workbench` 和 `内容测试工作台` 共用同一套 `workbench` 内核，差别只在权限和身份隔离。

## 先看什么

第一次接手项目，按这个顺序看：

1. [产品架构说明](./docs/product_architecture.md)
2. [使用说明](./docs/usage.md)
3. [Public Workbench 说明](./docs/public_workbench.md)
4. [内容测试工作台说明](./docs/content_workbench.md)
5. [运维面板说明](./docs/ops_dashboard.md)
6. [目录管理说明](./docs/directory_management.md)

## 正式入口

```powershell
python run_product.py
python run_generate_product.py --run-label generate_test
python run_qq_bot_service.py start
python run_public_workbench.py
```

`run_product.py` 跑完整产品链，`run_generate_product.py` 只跑生成层，`run_qq_bot_service.py` 控制 QQ 服务，`run_public_workbench.py` 启动公共网页入口。

## 私有工具入口

```powershell
python run_ops_dashboard.py
python run_content_workbench.py
```

运维面板地址是 [http://127.0.0.1:8765](http://127.0.0.1:8765)，私有工作台地址是 [http://127.0.0.1:8766](http://127.0.0.1:8766)，公共 workbench 本机地址是 [http://127.0.0.1:8767](http://127.0.0.1:8767)。

## 核心配置

人物资产入口在 [F:\openclaw-dev\workspace\projects\ig_roleplay_v3\config\character_assets.json](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/config/character_assets.json)，正文在 [F:\openclaw-dev\workspace\projects\ig_roleplay_v3\character\subject_profile.json](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/character/subject_profile.json)。

LLM 入口在 [F:\openclaw-dev\workspace\projects\ig_roleplay_v3\config\llm_profiles.json](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/config/llm_profiles.json)。

workbench 运行配置在 [F:\openclaw-dev\workspace\projects\ig_roleplay_v3\config\workbench_profiles.json](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/config/workbench_profiles.json)。

生图基座入口在 [F:\openclaw-dev\workspace\projects\ig_roleplay_v3\config\execution\active_profile.json](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/config/execution/active_profile.json)。

## 目录抓手

`src/workbench/` 是共享 workbench 内核，`src/public_web/` 是公共入口适配层，`src/studio/` 是私有测试适配层，`src/ops/` 是运维工具，`src/publish/` 是 QQ 产品入口，`tools/remote_access/` 放 public workbench 的公网接入脚本。Quick Tunnel 和正式 Tunnel 的用法都统一写在 [F:\openclaw-dev\workspace\projects\ig_roleplay_v3\docs\public_workbench.md](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/docs/public_workbench.md)。
