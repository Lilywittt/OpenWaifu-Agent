# 环境配置说明

## 必需条件

当前链路依赖两类外部资源：

1. 文本模型接口
2. 本地 ComfyUI 与共享 checkpoint

## `.env` 必需项

最少需要：

```env
DEEPSEEK_API_KEY=your_key_here
COMFYUI_ENDPOINT=http://127.0.0.1:8188
```

## `.env` 可选项

如果希望由执行层自动拉起本地 ComfyUI，可以额外配置：

```env
COMFYUI_INSTALL_ROOT=
COMFYUI_VENV_DIR=
COMFYUI_LOG_DIR=./runtime/service_logs/comfyui
COMFYUI_PID_DIR=./runtime/service_state
```

说明：

- `COMFYUI_INSTALL_ROOT`：ComfyUI 安装根目录
- `COMFYUI_VENV_DIR`：ComfyUI 所在 Python 环境目录
- `COMFYUI_LOG_DIR`：自动拉起时的日志输出目录
- `COMFYUI_PID_DIR`：自动拉起时的 pid 与状态目录

如果不填安装根和虚拟环境目录，代码会默认尝试使用共享上层目录：

- `F:\\openclaw-dev\\.local\\ComfyUI`
- `F:\\openclaw-dev\\.local\\comfyui-env`

## LLM 配置

当前文本模型配置在：

`config/creative_model.json`

当前默认是：

- provider: DeepSeek OpenAI-compatible API
- model: `deepseek-chat`

## 生图基座

当前执行层使用共享 checkpoint：

`animagine-xl-4.0-opt.safetensors`

默认配置位置：

- profile: `config/execution/comfyui_local_animagine_xl.json`
- workflow: `config/workflows/comfyui/animagine_xl_basic.workflow.json`

共享 checkpoint 实际路径由 profile 指向：

`../../../.local/ComfyUI/models/checkpoints/animagine-xl-4.0-opt.safetensors`

## 配置检查建议

第一次运行前，建议确认：

1. `DEEPSEEK_API_KEY` 已配置
2. `COMFYUI_ENDPOINT` 可访问
3. shared checkpoint 文件存在
4. ComfyUI workflow 模板可读
