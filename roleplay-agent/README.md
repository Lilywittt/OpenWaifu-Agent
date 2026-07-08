# OpenWaifu Roleplay Agent

OpenWaifu Roleplay Agent 是面向二次元角色扮演聊天的独立服务。核心能力是角色配置、长期对话、临时事件、世界书触发、DeepSeek 对话生成和 QQ 发布出口。

## 启动

配置界面：

```powershell
cd F:\openwaifu-workspace\roleplay-agent
python run_config_ui.py
```

QQ 发布出口：

```powershell
cd F:\openwaifu-workspace\roleplay-agent
python run_qq_publish_outlet.py start
python run_qq_publish_outlet.py status
python run_qq_publish_outlet.py stop
```

也可以双击根目录的 `打开OpenWaifu Roleplay Agent配置界面.cmd`。

## 配置

运行密钥放在 `.env`：

```env
DEEPSEEK_API_KEY=your_key_here
QQ_BOT_APP_ID=your_app_id
QQ_BOT_APP_SECRET=your_app_secret
QQ_BOT_USER_OPENID=
QQ_BOT_DISPLAY_NAME=
```

`.env` 已被 Git 忽略。仓库只提交 `.env.example`。

## 目录

```text
roleplay-agent/
  characters/          角色正文，每个角色一个 JSON 文件
  config/              模型、QQ、命令、发布桥接和 prompt manifest
  events/              临时事件
  lorebooks/           世界书
  personas/            用户人设
  prompts/             可人工编辑的 prompt 片段
  src/roleplay_agent/  服务代码
  tests/               单元测试
  runtime/             本地运行状态、日志、对话和缓存
```

角色索引保存在 `config/characters.json`，只记录版本、当前角色和排序。角色正文保存在 `characters/*.json`，便于人工审阅、迁移和版本管理。

## 验证

```powershell
cd F:\openwaifu-workspace\roleplay-agent
python -m unittest discover -s tests
python -m compileall src run_config_ui.py run_qq_publish_outlet.py run_qq_bot_service.py
```
