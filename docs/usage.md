# 产品使用说明

## 第一次上手

如果你是第一次运行这个项目，最推荐先做两件事：

1. 跑一轮完整产品链：

```powershell
python run_product.py
```

2. 启动 QQ 私聊服务：

```powershell
python tests/runners/qq_bot_generate_service_ctl.py start
```

然后去 QQ 私聊机器人发送：

```text
帮助
```

## 正式入口

完整产品链：

```powershell
python run_product.py
python run_product.py single --run-label my_test
python run_product.py single --run-label my_test --publish-target qq_bot_user
```

只跑生成层：

```powershell
python tests/runners/run_generate_product.py --run-label generate_test
```

QQ 私聊服务正式入口：

```powershell
python tests/runners/qq_bot_generate_service_ctl.py start
python tests/runners/qq_bot_generate_service_ctl.py status
python tests/runners/qq_bot_generate_service_ctl.py stop
python tests/runners/qq_bot_generate_service_ctl.py restart
```

## 调试入口

只在前台调试 QQ 私聊服务时使用：

```powershell
python tests/runners/qq_bot_generate_service.py
```

## 主要回放脚本

所有可执行 runner 都放在：

`tests/runners/`

常用几条：

- 从采样跑到场景稿：`python tests/runners/world_design_runner.py run --count 5 --label wd_review`
- 从已有场景稿直跑到生图：`python tests/runners/world_design_to_image_runner.py --source F:\path\to\01_world_design.json --count 1 --label scene_replay`
- 从已有采样输入直跑到生图：`python tests/runners/sample_to_image_runner.py --source F:\path\to\01_world_design_input.json --count 1 --label sample_replay`
- 从已有 creative package 直跑 prompt 和 execution：`python tests/runners/prompt_execution_runner.py --source F:\path\to\05_creative_package.json --count 1 --label prompt_replay`
- 独立回放社媒文案：`python tests/runners/social_post_runner.py --source F:\path\to\05_creative_package.json --count 1 --label social_review`

## QQ 私聊服务

当前交互方式为纯文本指令。

当前客户端会容忍少量常见误输入：
- 命令前后空格
- 外层引号
- 句末标点

但正式推荐仍然是直接发送裸命令。

体验者模式指令：
- `生成`
- `状态`
- `帮助`
- `/g`
- `/s`
- `/h`

开发者模式指令：
- `开发者模式`
- `注入场景稿`
- `体验者模式`
- `/d`
- `/i`
- `/e`

### 体验者模式

启动服务后，直接去 QQ 私聊机器人发送：

```text
生成
```

也可以发送：

```text
/g
```

生成过程中可发送：

```text
状态
帮助
```

也可以发送：

```text
/s
/h
```

### 开发者模式

启动服务后，按这个顺序操作：

1. 发送：
```text
开发者模式
```
2. 再发送：
```text
注入场景稿
```
也可以发送：
```text
/i
```
3. 然后直接发送场景设计正文，或发送一段 JSON：

```text
午后的旧书店阁楼里，主角踮脚从高处木书架抽出一本蒙尘厚书，阳光穿过斜顶小窗照在书页与漂浮灰尘上，画面安静而带一点发现秘密时的轻微紧张感。
```

```json
{
  "scenePremiseZh": "旧书店阁楼里的午后魔法",
  "worldSceneZh": "午后的旧书店阁楼里，主角踮脚从高处木书架抽出一本蒙尘厚书，阳光穿过斜顶小窗照在书页与漂浮灰尘上，画面安静而带一点发现秘密时的轻微紧张感。"
}
```

系统会把这份场景稿保存到：

```text
runtime/service_state/publish/qq_bot_scene_drafts/<user>/latest.json
```

然后直接从场景稿跑到出图。

进入注入态后，后续非命令消息会继续按新的场景稿处理；只有检测到命令，才会切回命令分支。

### 服务控制脚本

启动：

```powershell
python tests/runners/qq_bot_generate_service_ctl.py start
```

查看状态：

```powershell
python tests/runners/qq_bot_generate_service_ctl.py status
```

这条命令还会返回后台日志路径：
- `runtime/service_logs/publish/qq_bot_generate_service.stdout.log`
- `runtime/service_logs/publish/qq_bot_generate_service.stderr.log`
- `runtime/service_state/publish/qq_bot_generate_service/service_events.jsonl`

停止：

```powershell
python tests/runners/qq_bot_generate_service_ctl.py stop
```

完整说明见：

[qq_bot_private_service.md](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/docs/qq_bot_private_service.md)
