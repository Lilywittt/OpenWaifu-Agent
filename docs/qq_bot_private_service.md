# QQ 私聊生成服务

## 正式入口

统一使用这一条：

```powershell
python tests/runners/qq_bot_generate_service_ctl.py start
python tests/runners/qq_bot_generate_service_ctl.py status
python tests/runners/qq_bot_generate_service_ctl.py stop
python tests/runners/qq_bot_generate_service_ctl.py restart
```

前台调试才使用：

```powershell
python tests/runners/qq_bot_generate_service.py
```

这条前台脚本只用于调试。正式使用只认：

```powershell
python tests/runners/qq_bot_generate_service_ctl.py start
python tests/runners/qq_bot_generate_service_ctl.py status
python tests/runners/qq_bot_generate_service_ctl.py stop
python tests/runners/qq_bot_generate_service_ctl.py restart
```

## 当前可用交互

当前交互方式为纯文本指令。

为了降低误触成本，客户端现在会容忍一部分常见误输入：
- 指令前后的空格
- 外层引号，例如 `"生成"`、`“帮助”`
- 句末标点，例如 `生成。`、`状态！`

但正式指引仍然只推荐发送裸指令本身。

体验者模式支持：
- `生成`
- `状态`
- `帮助`
- `/g`
- `/s`
- `/h`

体验者模式的实际界面效果：
- `帮助`：返回一张纯文本说明面板
- `生成`：返回“已接收”回执，并提示预计耗时
- `状态`：返回模式、阶段、runId、队列和最近错误
- 完成后：直接回图片和社媒文案
- 失败时：返回错误摘要和下一步提示

开发者模式支持：
- `开发者模式`
- `体验者模式`
- `注入场景稿`
- `/d`
- `/e`
- `/i`

## 最短使用步骤

### 体验者模式

1. 启动服务：

```powershell
python tests/runners/qq_bot_generate_service_ctl.py start
```

2. 去 QQ 私聊机器人发送：

```text
生成
```

也可以直接发：

```text
/g
```

3. 如需查看进度，再发送：

```text
状态
```

也可以发：

```text
/s
```

### 开发者模式

1. 启动服务：

```powershell
python tests/runners/qq_bot_generate_service_ctl.py start
```

2. 去 QQ 私聊机器人发送：

```text
开发者模式
```

3. 再发送：

```text
注入场景稿
```

也可以直接发：

```text
/i
```

4. 然后直接发送场景设计内容，或发送一段 JSON 场景稿

纯文本示例：

```text
午后的旧书店阁楼里，主角踮脚从高处木书架抽出一本蒙尘厚书，阳光穿过斜顶小窗照在书页与漂浮灰尘上，画面安静而带一点发现秘密时的轻微紧张感。
```

JSON 示例：

```json
{
  "scenePremiseZh": "旧书店阁楼里的午后魔法",
  "worldSceneZh": "午后的旧书店阁楼里，主角踮脚从高处木书架抽出一本蒙尘厚书，阳光穿过斜顶小窗照在书页与漂浮灰尘上，画面安静而带一点发现秘密时的轻微紧张感。"
}
```

服务会：

1. 把这份场景稿保存到 `runtime/service_state/publish/qq_bot_scene_drafts/<user>/latest.json`
2. 按正式产品管线直接从场景稿跑到出图
3. 把图片和社媒文案回发到当前 QQ 私聊
4. 保持在注入态；之后你继续发送的非命令消息，会被当成新的场景稿覆盖运行

缓存规则：

- `latest.json` 永远覆盖为该用户最近一次注入的场景稿
- `history/` 每次注入都会追加一份历史快照
- `history/` 每个用户最多保留最近 `20` 份，超出的旧记录会自动清理

## 服务行为

- 同一时刻只跑一轮任务
- 新的 `生成` 或场景稿注入请求在忙碌时会被拒绝并提示忙碌，不会并发穿透
- 忙碌时不会偷偷堆积长队列；用户需要等上一轮完成后再触发下一轮
- 失败 run 会保留现场，不会删现场
- 残留锁会自动清理；`status` 和 `stop` 会同时检查锁文件和真实进程
- `stop` 会先停接新任务；如果当前正在生成，会等当前这一轮结束后再退出

## 状态与日志

- 状态文件：`runtime/service_state/publish/qq_bot_generate_service/latest_status.json`
- 事件流水：`runtime/service_state/publish/qq_bot_generate_service/service_events.jsonl`
- 后台 stdout：`runtime/service_logs/publish/qq_bot_generate_service.stdout.log`
- 后台 stderr：`runtime/service_logs/publish/qq_bot_generate_service.stderr.log`
- 每用户模式状态：`runtime/service_state/publish/qq_bot_private_state/users/`
- 开发者模式场景稿缓存：`runtime/service_state/publish/qq_bot_scene_drafts/<user>/`

`python tests/runners/qq_bot_generate_service_ctl.py status` 现在也会返回这几份日志和事件文件的位置。

## 交互规则

- 每次切换到 `体验者模式` 或 `开发者模式`，机器人都会主动回一条完整指引。
- 生成过程中：
  - `状态` 和 `帮助` 会正常回复，不会中断当前生成。
  - 只有命令消息才会尝试中断当前生成，并按新命令继续处理。
  - 非命令消息第一次会收到一条“当前正在生图，请稍等”的提示和指引面板。
  - 同一轮生成里，后续非命令消息不再重复回复。
  - 开发者模式下如果在忙碌时继续发送场景稿，会明确提示这次不会并发启动。

- 体验者模式下，`生成` / `/g` 才会真正触发生图；`注入场景稿` / `/i` 会明确提示这是开发者模式命令，不再误触发。
- 开发者模式下，`注入场景稿` / `/i` 才会进入注入态；`生成` / `/g` 会明确提示先退出到体验者模式，不再误触发。
- 开发者模式成功按场景稿生图一次后，会主动再发一条提醒：继续发送正文或 JSON 会继续注入测试，只有 `体验者模式` 或 `/e` 才会退出。
