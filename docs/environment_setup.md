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
```

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

- `config/execution/comfyui_local_animagine_xl.json`

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

也就是说：

- `checkpointPath` 决定“本机有没有这份模型”
- `checkpointName` 决定“ComfyUI 实际加载哪一个 checkpoint 名字”

这两个值最好保持一致，对应同一个文件名。

### 当前仓库里的默认值说明

仓库里的默认 profile 目前仍然指向一条开发机上的共享路径：

```text
../../../.local/ComfyUI/models/checkpoints/animagine-xl-4.0-opt.safetensors
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
