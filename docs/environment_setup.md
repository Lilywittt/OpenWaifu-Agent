# 环境配置说明

## 必需环境变量

根目录 `.env` 至少需要这些字段：

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

## 人物资产

正式链路通过 [config/character_assets.json](../config/character_assets.json) 指定人物资产文件。当前默认内容是：

```json
{
  "subjectProfilePath": "character/subject_profile.json"
}
```

`subjectProfilePath` 保存人物资产文件路径，推荐使用相对项目根目录的路径。正文位于 [character/subject_profile.json](../character/subject_profile.json)。

## LLM 配置

正式链路通过 [config/llm_profiles.json](../config/llm_profiles.json) 选择 creative 和 prompt guard 所使用的模型配置。当前默认内容是：

```json
{
  "creativeModelConfigPath": "config/creative_model.json",
  "promptGuardModelConfigPath": "config/prompt_guard_model.json"
}
```

[config/creative_model.json](../config/creative_model.json) 供 creative、social_post 和 prompt_builder 使用，[config/prompt_guard_model.json](../config/prompt_guard_model.json) 供 prompt guard 使用。

## 生图基座

当前默认 checkpoint 是 `animagine-xl-4.0-opt.safetensors`。推荐把模型文件放在自己 ComfyUI 安装目录下的 `models/checkpoints/` 中，例如：

```text
F:\ComfyUI\models\checkpoints\animagine-xl-4.0-opt.safetensors
```

对外使用时，最方便的做法是在 `.env` 里写明本机实际路径：

```env
COMFYUI_ENDPOINT=http://127.0.0.1:8188
COMFYUI_CHECKPOINT_PATH=F:\ComfyUI\models\checkpoints\animagine-xl-4.0-opt.safetensors
COMFYUI_CHECKPOINT_NAME=animagine-xl-4.0-opt.safetensors
```

执行层入口在 [config/execution/active_profile.json](../config/execution/active_profile.json)，当前具体 profile 在 [config/execution/comfyui_local_animagine_xl.json](../config/execution/comfyui_local_animagine_xl.json)。入口文件用于指定当前启用的 execution profile，具体 profile 维护 checkpoint、workflow、采样参数和节点映射。

执行层读取顺序是：先读 execution profile，再应用 `.env` 中的 `COMFYUI_CHECKPOINT_PATH` 和 `COMFYUI_CHECKPOINT_NAME` 覆盖，随后在本地校验 checkpoint 文件是否存在，最后把 `checkpointName` 写进 ComfyUI workflow 的 checkpoint loader 节点。

仓库里的默认 profile 仍指向开发机上的共享路径，所以对外使用时应优先通过 `.env` 改成自己机器上的实际路径。

## 网络

当前系统同时使用外网链路和本地链路。采样、LLM、QQ 网关和 QQ 消息接口都属于外网链路；ComfyUI 走本机地址 `http://127.0.0.1:8188`。代码已经把 `127.0.0.1`、`localhost` 和 `::1` 固定为本地直连，避免系统代理把本地生图流量转到外部代理。

## QQ 当前形态

当前落地的是文本私聊链路，支持私聊文本触发、私聊 markdown 回复和私聊图片回传。环境变量只需要覆盖这条现行私聊链路所需的字段。
