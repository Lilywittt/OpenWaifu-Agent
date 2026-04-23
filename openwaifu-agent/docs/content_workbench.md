# 内容测试工作台说明

私有内容测试工作台是你自己的调试入口，地址是 [http://127.0.0.1:8766](http://127.0.0.1:8766)。

常用命令：

```powershell
python run_content_workbench.py
python run_content_workbench.py status
python run_content_workbench.py stop
python run_content_workbench.py restart --no-open-browser
python run_content_workbench.py inventory
python run_content_workbench.py cleanup-report --older-than-days 14
python run_content_workbench.py delete-run --run-id 2026-04-11T21-11-48_01
```

代码分层：

- `src/workbench/`：共享 service、store、worker、views
- `src/studio/`：私有测试适配层
- `src/test_pipeline/core.py`：内容生成编排
- `src/run_detail_store.py`：run 详情读取

运行态目录：

- `runtime/runs/`：任务产物
- `runtime/service_state/shared/workbench/`：共享 workbench 状态
- `runtime/service_state/shared/review_favorites.jsonl`：收藏索引

私有工作台和体验工作台共用同一条生成链。私有工作台侧重目录审阅、收藏、删除和清理；体验工作台侧重生成和产物查看。
