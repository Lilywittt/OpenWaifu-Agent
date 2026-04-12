# 内容测试工作台说明

## 定位

内容测试工作台是本地 sidecar，用来调试内容链，不走 QQ。

它解决的是：

- 不想反复去 QQ 发消息
- 不想每次都敲 runner 命令
- 需要从不同起点重放到不同终点
- 需要直接看中间产物、Prompt 回调和最终图片

它不是：

- 运维面板
- QQ 私聊入口
- 第二套独立测试编排系统

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

地址：

- [http://127.0.0.1:8766](http://127.0.0.1:8766)

## 架构

代码分成 4 层：

- `src/studio/content_workbench_service.py`
  - 本地 HTTP 服务和 API
- `src/studio/content_workbench_worker.py`
  - 独立 worker 进程
- `src/studio/content_workbench_store.py`
  - 状态、历史、索引、删除和清理报告
- `src/studio/content_workbench_views.py`
  - 页面渲染

真正的测试编排不在 `src/studio/`，而在：

- `src/test_pipeline/core.py`

这层才是测试起点、终点和阶段推进的唯一真相。

## 当前支持的测试起点

- 实时采样全链路
- 场景稿正文
- 已有 `01_world_design.json`
- 采样内容正文
- 已有 `01_world_design_input.json`
- creative package 正文
- 已有 `05_creative_package.json`
- prompt package 正文
- 已有 prompt package

原则：

- 文本输入由前端自动补成对应结构
- 不要求用户手工拼 JSON 包装

## 当前支持的测试终点

- 场景稿
- 三份设计稿
- 社媒文案
- 最终 Prompt
- 生图

## 运行规则

- 同一时刻只允许一轮工作台测试运行
- 工作台和 QQ 服务可以同时在线，但不能同时占用生成链
- 如果共享执行位已被占用，工作台直接拒绝启动，不抢资源
- 停止是协作式中断，不承诺立刻硬停
- Web 服务重启不应该主动杀掉独立 worker；worker 退出后，本轮才进入终态

## 交互设计思路

这块的目标是减少鼠标移动和点击次数。

核心规则：

- 左侧只负责选测试
- 右侧只负责看详情和做少量操作
- 当前运行中的测试在左侧始终可见
- 左手键盘切换，右手鼠标只在右侧操作

键盘：

- `↑ / ↓`
- `Home / End`

右侧动作：

- 查看详情
- 上一条 / 下一条
- 删除当前目录
- 看图和看 Prompt 回调差异

## Prompt 回调展示

详情页支持：

- 回调报告
- 回调前后 Prompt 对比
- 变更片段高亮

重点是让测试者直接看到“改了哪里”，而不是盯着两段长文本人工比对。

## 索引和训练筛选

工作台会维护：

- `runtime/service_state/sidecars/content_workbench/run_index.jsonl`
- `runtime/service_state/sidecars/content_workbench/run_index.csv`

其中 `run_index.csv` 是后续人工筛选和训练选片的主入口。

它会记录：

- 时间
- 状态
- 起点
- 终点
- 场景标题
- 社媒文案预览
- Prompt 预览
- 图片路径
- run 目录

## 清理

先出报告，再人工确认，再删。

清理报告：

- `runtime/service_state/sidecars/content_workbench/cleanup_report.json`
- `runtime/service_state/sidecars/content_workbench/cleanup_report.csv`

命令：

```powershell
python run_content_workbench.py cleanup-report --older-than-days 14
```

删除指定 run：

```powershell
python run_content_workbench.py delete-run --run-id 2026-04-11T21-11-48_01
```

规则：

- 只删 `runtime/runs/<run_id>/`
- 不删当前运行中的目录
- 删完后索引同步标记为 deleted

## 产物和状态放哪

代码：

- `run_content_workbench.py`
- `src/studio/`
- `src/test_pipeline/`

状态和日志：

- `runtime/service_state/sidecars/content_workbench/`
- `runtime/service_logs/sidecars/content_workbench/`

正式测试 run：

- `runtime/runs/<run_id>/`
