# 内容测试工作台说明

## 定位

内容测试工作台是本地内容测试入口，地址是 [http://127.0.0.1:8766](http://127.0.0.1:8766)。它把测试前端和测试后端放在同一套说明里：前端负责输入、浏览和删除，后端负责 worker、状态、索引和测试编排。

## 启动和控制

```powershell
python run_content_workbench.py
python run_content_workbench.py status
python run_content_workbench.py stop
python run_content_workbench.py restart --no-open-browser
python run_content_workbench.py inventory
python run_content_workbench.py cleanup-report --older-than-days 14
python run_content_workbench.py delete-run --run-id 2026-04-11T21-11-48_01
```

## 前后端结构

`src/studio/content_workbench_service.py` 提供本地 HTTP 服务和 API，`src/studio/content_workbench_worker.py` 负责独立 worker，`src/studio/content_workbench_store.py` 管状态、历史、索引和清理，`src/studio/content_workbench_views.py` 渲染页面。测试编排核心在 [src/test_pipeline/core.py](../src/test_pipeline/core.py)，工作台与与之重合的批量 runner 都调用这一层。

## 支持的测试方式

起点支持实时采样全链路、场景稿正文、已有 `01_world_design.json`、采样内容正文、已有 `01_world_design_input.json`、creative package 正文、已有 `05_creative_package.json`、prompt package 正文和已有 prompt package。正文输入由前端自动补成对应结构。

终点支持场景稿、三份设计稿、社媒文案、最终 Prompt 和生图。

## 运行规则

同一时刻只允许一轮工作台测试运行。工作台和 QQ 服务可以同时在线，但共享生成执行位；如果执行位已被占用，工作台会直接返回忙碌状态。Web 服务重启不会主动杀掉独立 worker，worker 结束后这轮测试才进入终态。

## 页面交互

左侧用于切换测试，右侧用于看详情和做少量操作。当前运行中的测试始终保留在左侧可见位置，支持用 `↑`、`↓`、`Home`、`End` 快速切换。右侧详情里可以查看 Prompt 回调报告、回调前后高亮差异、图片，以及删除当前 run。

## 索引和清理

工作台会维护 [runtime/service_state/sidecars/content_workbench/run_index.jsonl](../runtime/service_state/sidecars/content_workbench/run_index.jsonl) 和 [runtime/service_state/sidecars/content_workbench/run_index.csv](../runtime/service_state/sidecars/content_workbench/run_index.csv)。`run_index.csv` 适合人工筛选和后续训练选片。

清理报告输出到 `runtime/service_state/sidecars/content_workbench/cleanup_report.json` 和 `cleanup_report.csv`。`cleanup-report` 先出候选，`delete-run` 再按 runId 删除 `runtime/runs/<run_id>/`，当前运行中的目录不会被删。

## 文件落点

工作台代码在 `run_content_workbench.py`、`src/studio/` 和 `src/test_pipeline/`。状态和日志在 `runtime/service_state/sidecars/content_workbench/` 与 `runtime/service_logs/sidecars/content_workbench/`。每轮测试的内容产物仍然统一落在 `runtime/runs/<run_id>/`。
