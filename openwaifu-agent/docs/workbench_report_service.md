# Workbench 报告监听服务

这个服务监听 workbench 新完成的 run，并把一张图加一段社媒文案推到 QQ。

## 适用范围

- 私有测试工作台 `8766`
- 内容体验工作台 `8767`

两边的终态 run 都会写入共享 workbench 索引，所以监听服务只需要盯这一份共享索引。

## 推送条件

服务只处理同时满足这两个条件的 run：

- 有最终图片
- 有社媒文案

服务启动后只监听**新完成**的 run。启动前已经结束的 run 不补发。

## 正式入口

```powershell
python run_workbench_report_service.py start
python run_workbench_report_service.py status
python run_workbench_report_service.py stop
python run_workbench_report_service.py restart
python run_workbench_report_service.py foreground
```

`start / status / stop / restart` 用于日常运维，`foreground` 用于本机调试。

## 配置

配置文件：

`config/reporting/workbench_report_service.json`

当前字段：

- `pollSeconds`：轮询间隔
- `qqTarget`：QQ 发送目标

`qqTarget` 复用 `config/publish/qq_bot_message.json` 这套 QQ 凭据配置。

## 代码结构

- `src/reporting/sources.py`：读取共享 workbench 索引，找出新完成且可推送的 run
- `src/reporting/package.py`：从 run detail 组装最小报告包
- `src/reporting/adapters/qq_report.py`：把图片和社媒文案发到 QQ
- `src/reporting/service.py`：轮询、去重、分发
- `src/reporting/state.py`：状态文件、事件流、已发送记录

## 运行态文件

- 状态目录：`runtime/service_state/reporting/workbench_report_service/`
- 日志目录：`runtime/service_logs/reporting/`

关键文件：

- `latest_status.json`
- `service_events.jsonl`
- `sent_reports.jsonl`

## 数据来源

监听服务只依赖两层现成接口：

- `studio.content_workbench_store.workbench_inventory_paths()`
- `run_detail_store.build_run_detail_snapshot()`

这样监听服务不需要自己去拼 `creative/`、`social_post/`、`execution/` 目录。
