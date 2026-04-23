# 目录管理说明

目录现在按“核心能力、公共入口、私有工具、外层接入”分。

`src/workbench/` 是共享 workbench 内核，里面放 service、store、worker、views、profile、identity。`src/studio/` 是私有工作台适配层，`src/public_web/` 是公共 workbench 适配层，`src/ops/` 是运维面板，`src/publish/` 是 QQ 产品入口。`src/test_pipeline/` 继续负责 richer 的内容生成编排，`src/run_detail_store.py` 继续负责 run 详情读取。

根目录入口现在有四个常用脚本：`run_ops_dashboard.py`、`run_content_workbench.py`、`run_public_workbench.py`、`run_qq_bot_service.py`。其中 `run_public_workbench.py` 是公共网页入口，`run_content_workbench.py` 是私有测试入口。

配置层也按职责分开：`config/character_assets.json` 管人物资产入口，`config/llm_profiles.json` 管文本模型，`config/workbench_profiles.json` 管 private/public workbench 的端口和标题，`config/execution/` 管生图基座。

运行态目录重点看这三处：`runtime/runs/` 放所有任务产物，`runtime/service_state/shared/workbench/` 放共享 workbench 状态，`runtime/service_state/shared/review_favorites.jsonl` 放共享收藏索引。`runtime/service_logs/sidecars/` 继续放私有和运维入口自己的日志；公网接入壳自己的日志单独放在 `runtime/service_logs/remote_access/`。

`tools/remote_access/` 只放公网接入模板和脚本，不放真实凭据。真实 `cloudflared` 凭据继续留在仓库外的本机目录。这样目录层级始终清楚：业务代码在 `src/`，运行配置在 `config/`，公网壳在 `tools/remote_access/`，运行态数据在 `runtime/`。
