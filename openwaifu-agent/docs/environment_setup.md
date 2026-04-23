# 环境配置说明

这份文档只回答三件事：`.env` 放什么、路径按什么规则解析、ComfyUI 在哪里。

## 根目录和路径规则

当前模块是 `openwaifu-agent/`，但工作区根目录是它的上一级。工作区根目录以 `ai_must_read.txt` 为标记。

路径规则已经固定：

- 项目内代码、配置、人物资产，按 **模块根目录** 解析
- `.local/...` 这类本机共享资源，按 **工作区根目录** 解析
- `runtime/...` 运行产物，按 **模块根目录** 解析

也就是说，当前默认本机资源位置是：

```text
<workspace-root>\.local\ComfyUI
<workspace-root>\.local\comfyui-env
```

工作区级共享资源统一落在 `<workspace-root>\.local\...`。

## 必需环境变量

模块根目录 `.env` 至少需要这些字段：

```env
DEEPSEEK_API_KEY=your_key_here
COMFYUI_ENDPOINT=http://127.0.0.1:8188
QQ_BOT_APP_ID=your_app_id
QQ_BOT_APP_SECRET=your_app_secret
QQ_BOT_USER_OPENID=your_user_openid
```

## 常用可选环境变量

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

`COMFYUI_INSTALL_ROOT` 和 `COMFYUI_VENV_DIR` 留空时，会默认落到工作区根目录下的 `.local/`。只有你本机放在别处时，才需要覆写。

## 人物资产和 LLM 配置

人物资产入口在 [config/character_assets.json](../config/character_assets.json)，默认正文文件是 [character/subject_profile.json](../character/subject_profile.json)。

LLM 配置在 [config/llm_profiles.json](../config/llm_profiles.json)。当前默认阶段映射全部走 `deepseek-chat`。`profiles` 定义模型池，`stages` 定义每个阶段实际选哪个模型。

## ComfyUI 执行层

执行层入口在 [config/execution/active_profile.json](../config/execution/active_profile.json)，当前具体 profile 在 [config/execution/comfyui_local_animagine_xl.json](../config/execution/comfyui_local_animagine_xl.json)。

当前 profile 里的默认 checkpoint 路径写成：

```text
.local/ComfyUI/models/checkpoints/animagine-xl-4.0-opt.safetensors
```

这表示它会从工作区根目录去找：

```text
<workspace-root>\.local\ComfyUI\models\checkpoints\animagine-xl-4.0-opt.safetensors
```

如果你机器上的 checkpoint 在别处，就在 `.env` 里覆写：

```env
COMFYUI_CHECKPOINT_PATH=F:\your-path\models\checkpoints\animagine-xl-4.0-opt.safetensors
COMFYUI_CHECKPOINT_NAME=animagine-xl-4.0-opt.safetensors
```

执行层读取顺序是：

1. 读取 execution profile
2. 用 `.env` 中的 `COMFYUI_CHECKPOINT_PATH` / `COMFYUI_CHECKPOINT_NAME` 覆盖
3. 校验本地 checkpoint 文件是否存在
4. 把最终 `checkpointName` 写进 workflow

## 网络

ComfyUI 走本机 `127.0.0.1`。采样、LLM、QQ 网关和公网接入属于外网链路，本地生图链路与它们分开处理。
