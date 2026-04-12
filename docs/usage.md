# 使用说明

## 在哪里运行

所有正式入口都在项目根目录运行：

- [F:\openclaw-dev\workspace\projects\ig_roleplay_v3](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3)

```powershell
cd /d F:\openclaw-dev\workspace\projects\ig_roleplay_v3
```

## 最常用的 5 个入口

```powershell
python run_product.py
python run_generate_product.py --run-label generate_test
python run_qq_bot_service.py start
python run_ops_dashboard.py
python run_content_workbench.py
```

对应含义：

- `run_product.py`：完整产品链
- `run_generate_product.py`：只跑生成层
- `run_qq_bot_service.py`：QQ 私聊服务
- `run_ops_dashboard.py`：运维面板
- `run_content_workbench.py`：内容测试工作台

## QQ 服务

```powershell
python run_qq_bot_service.py start
python run_qq_bot_service.py status
python run_qq_bot_service.py stop
python run_qq_bot_service.py restart
python run_qq_bot_service.py foreground
```

说明：

- `start / status / stop / restart` 是正式运维命令
- `foreground` 只用于本机调试

## 运维面板

```powershell
python run_ops_dashboard.py
python run_ops_dashboard.py --no-open-browser
python run_ops_dashboard.py --foreground
python run_ops_dashboard.py status
python run_ops_dashboard.py stop
python run_ops_dashboard.py restart --no-open-browser
```

地址：

- [http://127.0.0.1:8765](http://127.0.0.1:8765)

它只负责 QQ 服务运维，不负责本地内容测试。

## 内容测试工作台

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

地址：

- [http://127.0.0.1:8766](http://127.0.0.1:8766)

它不走 QQ 网关，直接调用本地内容链。

## QQ 服务和工作台能否同时开

可以同时在线，但不能同时占用本机生成链。

共享执行位在：

- `runtime/service_state/shared/generation_slot.json`

规则：

- QQ 服务和工作台都先申请共享执行位
- 谁先占用，另一边就收到明确忙碌反馈
- 不允许静默抢资源

## 工作台适合做什么

- 从实时采样跑完整链路
- 从场景稿、creative package、prompt package 等中间起点重放
- 看中间产物、Prompt 回调前后差异和最终图片
- 复跑最近一次测试
- 导出索引和清理报告
- 删除指定测试 run 目录

交互思路：

- 左手键盘用 `↑ / ↓ / Home / End` 切换左侧测试
- 右手鼠标只在右侧详情区做查看、删除和切换

## 工作台索引和清理

```powershell
python run_content_workbench.py inventory
python run_content_workbench.py cleanup-report --older-than-days 14
python run_content_workbench.py delete-run --run-id 2026-04-11T21-11-48_01
```

索引路径：

- `runtime/service_state/sidecars/content_workbench/run_index.jsonl`
- `runtime/service_state/sidecars/content_workbench/run_index.csv`

清理报告路径：

- `runtime/service_state/sidecars/content_workbench/cleanup_report.json`
- `runtime/service_state/sidecars/content_workbench/cleanup_report.csv`

说明：

- `run_index.csv` 适合人工筛选和训练选片
- `cleanup_report.*` 只出候选，不自动删
- `delete-run` 只删 `runtime/runs/<run_id>/`，并且不会删当前运行中的目录

## 批量回放入口

`tests/runners/` 只放批量回放和链路验证。

与工作台功能重合的 batch runner 会复用：

- `src/test_pipeline/core.py`

常用脚本：

- `tests/runners/sampling_to_scene_draft_runner.py`
- `tests/runners/scene_draft_to_image_runner.py`
- `tests/runners/scene_draft_downstream_runner.py`
- `tests/runners/sample_to_image_runner.py`
- `tests/runners/prompt_execution_runner.py`
- `tests/runners/social_post_runner.py`
- `tests/runners/publish_from_package_runner.py`
- `tests/runners/full_product_publish_runner.py`

示例：

```powershell
python tests/runners/sampling_to_scene_draft_runner.py --count 5 --label wd_review
python tests/runners/scene_draft_to_image_runner.py --source F:\path\to\01_world_design.json --count 1 --label scene_replay
python tests/runners/sample_to_image_runner.py --source F:\path\to\01_world_design_input.json --count 1 --label sample_replay
python tests/runners/prompt_execution_runner.py --source F:\path\to\05_creative_package.json --count 1 --label prompt_replay
python tests/runners/social_post_runner.py --source F:\path\to\05_creative_package.json --count 1 --label social_review
```

## 相关文档

- [QQ 私聊服务说明](./qq_bot_private_service.md)
- [运维面板说明](./ops_dashboard.md)
- [内容测试工作台说明](./content_workbench.md)
- [目录管理说明](./directory_management.md)
