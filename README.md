# ig_roleplay_v3

`v3` is a clean rewrite with only two layers:

- the creative layer decides what this run should depict
- the render layer turns that decision into prompts, workflow, and an image

Runtime output is one run per folder:

```text
runtime/
  runs/
    <run_id>/
      input/
      creative/
      render/
      output/
      trace/
  latest.json
```

`v3` only reads its own project-local `.env`:

```text
F:\openclaw-dev\workspace\projects\ig_roleplay_v3\.env
```

It does not read the machine-root `.env`.

All environment-bound dependencies belong here, including creative-model keys, optional remote image-provider keys, and local ComfyUI settings:

```env
DEEPSEEK_API_KEY=your_key_here
OPENAI_API_KEY=
ZHIPU_API_KEY=
DASHSCOPE_API_KEY=
COMFYUI_ENDPOINT=http://127.0.0.1:8188
COMFYUI_INSTALL_ROOT=
COMFYUI_VENV_DIR=
COMFYUI_LOG_DIR=./runtime/service_logs/comfyui
COMFYUI_PID_DIR=./runtime/service_state
```
