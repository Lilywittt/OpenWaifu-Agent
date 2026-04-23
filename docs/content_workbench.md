# 内容测试工作台说明

私有内容测试工作台是你自己的调试入口，地址是 [http://127.0.0.1:8766](http://127.0.0.1:8766)。它跑在共享 `workbench` 内核之上，但保留全部私有能力，所以你可以发起 richer 任务、审阅任意本地路径、收藏、删目录、看清理报告。

启动和控制命令还是这些：

```powershell
python run_content_workbench.py
python run_content_workbench.py status
python run_content_workbench.py stop
python run_content_workbench.py restart --no-open-browser
python run_content_workbench.py inventory
python run_content_workbench.py cleanup-report --older-than-days 14
python run_content_workbench.py delete-run --run-id 2026-04-11T21-11-48_01
```

代码分层现在是：`src/workbench/` 放共享 service、store、worker、views；`src/studio/` 只保留私有适配层；`src/test_pipeline/core.py` 继续做内容生成编排；`src/run_detail_store.py` 继续做结果读取。私有工作台和公共 workbench 都复用同一条生成链和结果读取链。

工作台运行状态现在统一落在 [F:\openclaw-dev\workspace\projects\ig_roleplay_v3\runtime\service_state\shared\workbench](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/runtime/service_state/shared/workbench)，不再放在旧的 `sidecars/content_workbench` 目录里。收藏索引单独放在 [F:\openclaw-dev\workspace\projects\ig_roleplay_v3\runtime\service_state\shared\review_favorites.jsonl](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/runtime/service_state/shared/review_favorites.jsonl)。每轮任务的内容产物仍然统一落在 `runtime/runs/<run_id>/`。

页面语义已经改成“任务”而不是“测试”，但私有工作台仍然保留全部测试能力。左侧用于切换任务，右侧用于看详情和做少量操作；支持收藏筛选、目录审阅、Prompt 对比、图片查看和删除保护。共享执行位仍然只有一条，所以私有工作台、公共 workbench 和 QQ 产品链会竞争同一个本机生成执行位。
