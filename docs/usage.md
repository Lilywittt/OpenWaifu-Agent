# 使用说明

## 在哪里运行

所有入口都在项目根目录运行：

- [F:\openclaw-dev\workspace\projects\ig_roleplay_v3](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3)

```powershell
cd /d F:\openclaw-dev\workspace\projects\ig_roleplay_v3
```

## 正式产品

正式产品常用入口只有三条：

```powershell
python run_product.py
python run_generate_product.py --run-label generate_test
python run_qq_bot_service.py start
```

`run_product.py` 跑完整产品链，`run_generate_product.py` 只跑生成层，`run_qq_bot_service.py` 控制 QQ 私聊服务。

QQ 服务常用命令如下：

```powershell
python run_qq_bot_service.py start
python run_qq_bot_service.py status
python run_qq_bot_service.py stop
python run_qq_bot_service.py restart
python run_qq_bot_service.py foreground
```

## 开发工具

开发工具分成运维和测试两块。

运维面板入口如下：

```powershell
python run_ops_dashboard.py
python run_ops_dashboard.py --no-open-browser
python run_ops_dashboard.py --foreground
python run_ops_dashboard.py status
python run_ops_dashboard.py stop
python run_ops_dashboard.py restart --no-open-browser
```

地址是 [http://127.0.0.1:8765](http://127.0.0.1:8765)。

内容测试工作台入口如下：

```powershell
python run_content_workbench.py
python run_content_workbench.py --no-open-browser
python run_content_workbench.py --foreground
python run_content_workbench.py status
python run_content_workbench.py stop
python run_content_workbench.py restart --no-open-browser
python run_content_workbench.py inventory
python run_content_workbench.py cleanup-report --older-than-days 14
python run_content_workbench.py delete-run --run-id 2026-04-11T21-11-48_01
```

地址是 [http://127.0.0.1:8766](http://127.0.0.1:8766)。

## 并行规则

QQ 服务和内容测试工作台可以同时在线，但共用同一条本机生成链。共享执行位在 `runtime/service_state/shared/generation_slot.json`。谁先占用，谁先进入生成阶段；另一边会收到明确的忙碌状态。

## 批量回放

`tests/runners/` 保留批量回放和链路验证脚本。与工作台能力重合的批量脚本统一复用 [src/test_pipeline/core.py](../src/test_pipeline/core.py)。当前常用入口包括 `sampling_to_scene_draft_runner.py`、`scene_draft_to_image_runner.py`、`scene_draft_downstream_runner.py`、`sample_to_image_runner.py`、`prompt_execution_runner.py`、`social_post_runner.py`、`publish_from_package_runner.py` 和 `full_product_publish_runner.py`。

## 相关文档

1. [产品架构说明](./product_architecture.md)
2. [技术思路说明](./technical_strategy.md)
3. [QQ 私聊服务说明](./qq_bot_private_service.md)
4. [运维面板说明](./ops_dashboard.md)
5. [内容测试工作台说明](./content_workbench.md)
6. [目录管理说明](./directory_management.md)
