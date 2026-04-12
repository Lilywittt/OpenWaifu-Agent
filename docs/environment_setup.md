# 环境配置说明

## 必需环境变量

根目录 `.env` 至少需要：

```env
DEEPSEEK_API_KEY=your_key_here
COMFYUI_ENDPOINT=http://127.0.0.1:8188
QQ_BOT_APP_ID=your_app_id
QQ_BOT_APP_SECRET=your_app_secret
QQ_BOT_USER_OPENID=your_user_openid
```

## 可选环境变量

```env
COMFYUI_INSTALL_ROOT=
COMFYUI_VENV_DIR=
COMFYUI_CHECKPOINT_PATH=
COMFYUI_CHECKPOINT_NAME=animagine-xl-4.0-opt.safetensors
COMFYUI_LOG_DIR=./runtime/service_logs/comfyui
COMFYUI_PID_DIR=./runtime/service_state
QQ_BOT_GROUP_OPENID=
QQ_BOT_DISPLAY_NAME=
```

## 原始人物资产怎么配置

正式链路使用一份显式配置来指定人物原始资产路径：

- [character_assets.json](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/config/character_assets.json)

当前默认内容是：

```json
{
  "subjectProfilePath": "character/subject_profile.json"
}
```

规则只有两条：

- `subjectProfilePath` 只负责指定路径，不承载人物正文
- 路径建议写成相对项目根目录的相对路径，便于迁移和版本管理

默认人物资产本体在：

- [subject_profile.json](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/character/subject_profile.json)

## LLM 模型配置怎么维护

正式链路使用一份显式配置来指定 creative 层和 prompt guard 层各自读取哪份模型配置：

- [llm_profiles.json](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/config/llm_profiles.json)

当前默认内容是：

```json
{
  "creativeModelConfigPath": "config/creative_model.json",
  "promptGuardModelConfigPath": "config/prompt_guard_model.json"
}
```

默认情况下：

- [creative_model.json](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/config/creative_model.json) 供 creative 和 social_post / prompt_builder 复用
- [prompt_guard_model.json](/F:/openclaw-dev/workspace/projects/ig_roleplay_v3/config/prompt_guard_model.json) 供 prompt guard 单独使用

规则：

- `llm_profiles.json` 只维护路径选择
- 具体模型配置文件只维护模型、温度、base_url、token_limit 等正文

## 生图模型基座怎么配置

当前执行层默认使用的 checkpoint 是：

- `animagine-xl-4.0-opt.safetensors`

推荐你把模型文件放在 **自己的 ComfyUI 安装目录** 下：

```text
<你的 ComfyUI 根目录>/models/checkpoints/animagine-xl-4.0-opt.safetensors
```

例如：

```text
F:\ComfyUI\models\checkpoints\animagine-xl-4.0-opt.safetensors
```

最推荐的配置方式不是去改仓库里的 JSON，而是在根目录 `.env` 里覆盖：

```env
COMFYUI_ENDPOINT=http://127.0.0.1:8188
COMFYUI_CHECKPOINT_PATH=F:\ComfyUI\models\checkpoints\animagine-xl-4.0-opt.safetensors
COMFYUI_CHECKPOINT_NAME=animagine-xl-4.0-opt.safetensors
```

### 项目里是怎么引用它的

执行层配置文件在：

- `config/execution/active_profile.json`
- `config/execution/comfyui_local_animagine_xl.json`
- `config/prompt_guard_model.json`

补充说明：

- `config/execution/active_profile.json` 是正式入口，只负责指定当前启用哪一份 execution profile
- 具体 execution profile 负责维护 checkpoint、workflow、采样参数和节点映射
- 正式链路先读 `active_profile.json`，再定位到具体 profile
- `.env` 里的 `COMFYUI_CHECKPOINT_PATH` / `COMFYUI_CHECKPOINT_NAME` 仍然只是本机覆盖层

其中：

- `active_profile.json`
  只负责指定当前正式链路启用哪一份 execution profile
- 具体 execution profile
  负责维护 checkpoint、workflow、采样参数和节点映射

它同时持有两项信息：

- `checkpointPath`
  作用：本地校验模型文件是否真的存在
- `checkpointName`
  作用：注入到 ComfyUI workflow 的 `ckpt_name`

当前代码引用顺序是：

1. `src/execution/workflow.py`
   先读取 execution profile
2. 如果 `.env` 里配置了 `COMFYUI_CHECKPOINT_PATH` / `COMFYUI_CHECKPOINT_NAME`
   就优先使用环境变量覆盖
3. `src/execution/pipeline.py`
   会先检查 `checkpointPath` 指向的文件是否存在
4. `src/execution/workflow.py`
   再把 `checkpointName` 写进 ComfyUI workflow 的 checkpoint loader 节点

Prompt 回调层默认单独使用：

- `config/prompt_guard_model.json`

它和 creative 层一样走 DeepSeek OpenAI-compatible 配置，但职责单独拆开，便于后续独立调温度、模型和限额。

也就是说：

- `checkpointPath` 决定“本机有没有这份模型”
- `checkpointName` 决定“ComfyUI 实际加载哪一个 checkpoint 名字”

这两个值最好保持一致，对应同一个文件名。

### 当前仓库里的默认值说明

仓库里的默认 profile 目前仍然指向一条开发机上的共享路径：

```text
../../../.local/ComfyUI/models/checkpoints/animagine-xl-4.0-opt.safetensors
```

而当前默认启用的 execution profile 是：

```text
config/execution/comfyui_local_animagine_xl.json
```

这是当前开发环境的本机默认值，不建议别人直接照搬。
对外使用时，请优先通过 `.env` 覆盖成你自己机器上的实际路径。

## 网络原则

当前系统有两类网络：

1. 外网链路  
   采样、LLM、QQ bot 网关、QQ 发消息接口都属于这一类。

2. 本地链路  
   ComfyUI 只应该走 `http://127.0.0.1:8188`。

当前代码已经把 `127.0.0.1 / localhost / ::1` 强制设为本地直连，避免系统代理把本地生图流量错误转发到外部代理。

## QQ 私聊当前形态

当前落地形态只有：

- 私聊文本触发
- 私聊 markdown 回复
- 私聊图片回传

当前只需要配置现行文本私聊链路所需的字段。 
