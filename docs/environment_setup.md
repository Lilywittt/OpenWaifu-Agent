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
COMFYUI_LOG_DIR=./runtime/service_logs/comfyui
COMFYUI_PID_DIR=./runtime/service_state
QQ_BOT_GROUP_OPENID=
```

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

当前不要在配置里加按钮相关字段。按钮模板或自定义 keyboard 没有在现行产品里启用。 
