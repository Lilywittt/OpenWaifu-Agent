# ComfyUI 技术美术工作流计划

## 结论

OpenWaifu-Agent 的生图层下一步应从 ComfyUI 工作流本身开始升级。当前 graph 已经能把 Prompt Builder 和 Prompt Guard 的结果提交给 ComfyUI 并产出图片，但它仍然是最小 txt2img 链路：checkpoint、正负提示词、空 latent、KSampler、VAE decode、保存图片。这个链路适合验证端到端流程，继续承担正式默认生图会限制角色一致性、动作可控性、候选筛选、局部修复和发布规格导出。

新的目标是把生图层整理成可切换的技术美术工作流。简单版服务快速稳定出图，复杂版服务高权限工作台和本地精修；两套工作流共享执行入口、输入输出契约和 artifact 结构，内部 graph 按质量目标分层演进。

## 当前用户要求

当前阶段只做调研、计划和文档化。执行配置、active profile、workflow JSON 保持原样，实施阶段再进入代码和配置改动。

生图工作流必须支持简单版和复杂版切换。公网体验默认使用简单版，私有测试工作台允许选择复杂版。切换能力要走明确字段和统一接口，避免靠手工改 JSON 文件完成运行模式切换。

工作流优化必须面向技术美术管线，重点覆盖构图控制、角色一致性、候选图、局部修复、高清完成稿和平台规格导出。只调整 sampler、steps、CFG 的方案价值有限，不能作为本轮工作的主要成果。

代码和目录结构要保持清晰。已有执行层、工作台和 runtime artifact 能升级复用时优先复用；新增能力要进入明确目录和配置契约，避免把旧代码架空后另起一套并行入口。

中文文档、运行报告、批量验收结果和 artifact 都要按 UTF-8 处理。当前历史 run 中已经能看到部分中文乱码，后续做执行层验收时需要把编码链路纳入检查项。

## 当前基线

现有 workflow 模板位于 `config/workflows/comfyui/animagine_xl_basic.workflow.json`。节点拓扑为：

```text
CheckpointLoaderSimple
  -> CLIPTextEncode positive
  -> CLIPTextEncode negative
  -> EmptyLatentImage
  -> KSampler
  -> VAEDecode
  -> SaveImage
```

执行配置位于 `config/execution/comfyui_local_animagine_xl.json`。当前 profile 通过节点 ID 绑定 checkpoint、正向提示词、负向提示词、latent 尺寸、sampler 参数和输出节点。实际运行会写出 `00_execution_input.json`、`01_workflow_request.json`、`02_submit_response.json`、`03_workflow_history.json`、`04_execution_package.json`。

本机 ComfyUI 当前可用状态：

- ComfyUI 版本：`0.18.1`
- GPU：`NVIDIA GeForce RTX 3060 Laptop GPU`，6GB 显存级别
- checkpoint：`animagine-xl-4.0-opt.safetensors`
- LoRA、ControlNet、upscale model：目录存在，实际模型库存为空
- 可用内置节点包含 `KSamplerAdvanced`、`LatentUpscaleBy`、`ImageScale`、`VAEDecodeTiled`、`FreeU_V2`
- 可用自定义节点仅见 `SaveImageWebsocket`

近期运行记录显示，当前默认参数为 `1152x1440`、`35 steps`、`CFG 6.5`、`dpmpp_2m_sde`、`sgm_uniform`，单张图片耗时大致在 `66-120s`。这说明基础链路可用，但默认成本偏重，缺少候选阶段和完成稿阶段的边界。

## 行业工作流判断

成熟的技术美术生图管线围绕可控性组织。有效工作流会先确定角色资产与构图约束，再生成候选图，随后把有潜力的候选图送入局部修复和高清完成稿阶段。这个过程强调输入资产、控制图、候选选择、修复策略和导出规格的连续管理。

角色一致性应沉淀成模型资产。短期可以用角色描述、参考图和 IP-Adapter 辅助；长期应训练角色 LoRA，把发型、脸型、核心配饰和整体气质固化为可复用资产。

构图和姿态应引入控制条件。ControlNet/OpenPose/Depth/Lineart 适合把姿态、空间层次和轮廓传给扩散模型。对于自动采样主链路，控制条件可以先保持可选；对于高权限工作台，参考图、姿势图和已有图复跑应逐步进入 controlled workflow。

候选图和完成稿要分层。候选阶段关注构图、角色状态和画面方向，成本要低；完成稿阶段对选中图进行低 denoise 精修、局部 detail、高清化和平台规格导出。这样才能把 GPU 时间花在值得继续加工的图上。

## 推荐目标结构

### `simple`

简单版用于公网体验、自动主链路和快速验证。它依赖当前已有 checkpoint 和 ComfyUI 内置节点，优先保证稳定、速度和可复现。

推荐 graph：

```text
CheckpointLoaderSimple
  -> CLIPTextEncode positive
  -> CLIPTextEncode negative
  -> EmptyLatentImage
  -> KSampler
  -> VAEDecode
  -> ImageScale
  -> SaveImage
```

推荐默认策略：

- 基础生成尺寸贴近 Animagine XL 4.0 推荐尺度，例如 4:5 使用 `896x1120` 或 `896x1152`
- 采样器使用 `Euler Ancestral`
- steps 使用 `28`
- CFG 使用 `5`
- 最终导出 `1080x1350`

简单版的产物可直接交给发布层。它也承担回归基线，后续复杂版效果评估都要拿它对照。

### `complex_v1`

复杂版第一阶段使用当前本机已有节点完成二阶段精修，适合私有测试工作台和本地精修。它在资源尚未补齐时也能落地。

推荐 graph：

```text
CheckpointLoaderSimple
  -> FreeU_V2 optional
  -> CLIPTextEncode positive
  -> CLIPTextEncode negative
  -> EmptyLatentImage
  -> KSampler base
  -> LatentUpscaleBy
  -> KSampler refine
  -> VAEDecodeTiled
  -> ImageScale
  -> SaveImage
```

推荐策略：

- base pass 负责整体构图和主体稳定
- latent upscale 用于提升细节承载
- refine pass 使用低 denoise，建议从 `0.25-0.35` 试验
- tiled decode 降低显存压力
- 最终导出同样保持 `1080x1350`

这版复杂工作流先解决“单次基础采样直接当最终图”的问题，为后续 ControlNet、LoRA、Detailer 接入提供稳定骨架。

### `complex_v2`

复杂版第二阶段引入完整技术美术资产。它面向高权限工作台、批量审图和可继续加工的生产流程。

目标能力：

- 角色 LoRA：提高角色脸型、发型、核心配饰和整体气质的一致性
- IP-Adapter：支持角色参考图、风格参考图和短期参考约束
- ControlNet/OpenPose/Depth/Lineart：支持姿态、空间层次和轮廓控制
- Detailer：处理脸、手、肢体连接、衣物边缘和小道具
- Upscale model：输出高清完成稿和平台规格图

这版需要配套资源管理：模型下载路径、hash、版本、节点包版本、安装脚本、smoke 检查和失败诊断。

## 切换契约

执行入口增加 `executionPreset` 字段，合法值先定义为：

```json
{
  "executionPreset": "simple"
}
```

或：

```json
{
  "executionPreset": "complex"
}
```

默认值为 `simple`。公网体验工作台固定默认值；私有测试工作台显示切换控件；脚本和 QQ bot 可以通过请求字段传入，未传入时走默认值。

执行层根据 preset 解析到对应 profile 和 workflow 模板。`run_execution_pipeline` 接收解析后的 preset 或 profile path，最终把以下字段写入 `04_execution_package.json` 和 `run_summary.json`：

```json
{
  "executionPreset": "simple",
  "profileId": "comfyui_animagine_xl_simple_v1",
  "workflowId": "animagine_xl_simple_v1",
  "workflowVersion": "1.0.0"
}
```

简单版和复杂版共享这些输入：

- positive prompt
- negative prompt
- seed / seedSalt
- aspect ratio
- runId
- checkpoint name
- output directory

两套工作流共享这些输出：

- generated image path
- ComfyUI prompt id
- workflow request
- workflow history
- execution receipt
- timing and status metadata

## 工作台行为

私有测试工作台在任务表单中增加“生图工作流”选择。选项建议显示为：

- `快速出图`
- `精修工作流`

字段值分别对应 `simple` 和 `complex`。上一次请求、复跑和历史记录要保留该字段。运行详情展示当前 preset、profile、workflow 和关键参数。

公网体验工作台使用 `simple`。公共入口的任务耗时和失败率更敏感，复杂版适合留在高权限工作台验证成熟后再开放。

## 目录计划

后续实施时建议整理为：

```text
config/workflows/comfyui/
  simple/
    animagine_xl_simple_v1.workflow.json
  complex/
    animagine_xl_complex_v1.workflow.json
    animagine_xl_complex_v2.workflow.json

config/execution/
  presets.json
  profiles/
    comfyui_animagine_xl_simple_v1.json
    comfyui_animagine_xl_complex_v1.json

tools/comfyui/
  audit_resources.py
  smoke_workflow.py
  README.md
```

`presets.json` 负责把 `simple`、`complex` 映射到 profile。profile 负责绑定 workflow、模型资源、节点输入和默认参数。workflow JSON 只保存 ComfyUI graph。

## 验收计划

第一步做 workflow smoke。它检查 ComfyUI 健康、队列、模型库存、节点可用性、profile 绑定、workflow request 构造和输出节点。默认 dry-run，显式传入生成参数时再提交真实任务。

第二步做 simple/complex A/B 对照。选取 10 个已有 prompt package，分别跑 simple 和 complex，输出图片网格、耗时、失败率、输出尺寸、workflow request 和 execution package。

第三步做人工审图表。审图维度包括角色一致性、动作遵循度、构图稳定性、脸手问题、服装边缘、场景层次、发布尺寸合格性和继续加工价值。

第四步基于审图结果决定默认策略。simple 继续服务自动主链路；complex 在耗时、失败率和质量收益稳定后进入私有工作台常用入口。

## 外部依据

- Animagine XL 4.0 模型卡：`https://huggingface.co/cagliostrolab/animagine-xl-4.0`
- ControlNet 论文：`https://arxiv.org/abs/2302.05543`
- IP-Adapter：`https://github.com/tencent-ailab/IP-Adapter`
- ComfyUI 预处理器文档：`https://docs.comfy.org/tutorials/utility/preprocessors`
- ComfyUI 服务端路由：`https://docs.comfy.org/development/comfyui-server/comms_routes`
- ComfyUI Workflow JSON 规范：`https://docs.comfy.org/specs/workflow_json`
