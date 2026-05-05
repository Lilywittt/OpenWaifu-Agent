# ComfyUI 技术美术链路调研范围

## 调研目标

这次调研要回答一个具体问题：OpenWaifu-Agent 的生图执行层怎样从当前的基础文生图 demo，升级成更接近技术美术生产过程的工作流。重点不是继续微调 sampler、步数和 CFG，而是搞清楚输入图、参考图、局部修复、结构控制、高清导出在成熟项目里分别承担什么职责，哪些能力适合进入当前项目，哪些能力需要等资源和交互条件补齐后再做。

当前项目已经有 Agent 产出设计稿、Prompt Builder 编译提示词、Prompt Guard 审查提示词、ComfyUI 执行、run artifact 归档和工作台交互。生图层的短板集中在图像加工阶段：生成结果一旦有潜力，系统还缺少继续修、局部改、放大导出、复用参考图和沉淀好图偏好的能力。调研的核心目标就是把这些能力拆清楚，形成可实施的执行模式。

## 当前基线

本地 ComfyUI 服务可用，版本为 `0.18.1`，GPU 为 RTX 3060 Laptop 级别，显存约 6GB。当前项目使用 `config/workflows/comfyui/animagine_xl_basic.workflow.json`，链路是 checkpoint、正负提示词、空 latent、采样、解码和保存图片。这个 workflow 实际是文生图，没有输入图编码、mask、ControlNet、IP-Adapter、高清放大和局部修复。

模型资源方面，当前 checkpoint 有 `animagine-xl-4.0-opt.safetensors`。LoRA、ControlNet、upscale model 等目录存在，但真实模型库存不足。ComfyUI 节点层面能看到图生图、inpaint、ControlNet、局部 mask、高清放大相关节点，但项目执行配置和 workflow 还没有把这些能力组织成可调用产品功能。

## 需要搞清楚的问题

第一，基座模型的图生图能力能解决什么。要确认输入图和修改 prompt 进入 ComfyUI 后，适合做整体风格强化、光影调整、轻度重绘，还是能承担精确结构修改。当前判断是：普通图生图可以让一张图沿着 prompt 继续变化，但对“只改右手”“只换局部道具”“保留姿势只改衣服褶皱”这类任务控制力不足。精确修改需要 mask、局部 inpaint、自动分割、检测修复或专门图像编辑模型参与。

第二，局部修复在成熟技术美术工具里怎么组织。需要重点看用户怎样指定区域，系统怎样生成 mask，模型怎样只处理局部，修复结果怎样回到画布或 run artifact。这个问题直接关系到工作台设计：用户不应该只能重新跑整张图，应该能把一张好图继续加工。

第三，ControlNet 应该放在哪个位置。当前已经明确：ControlNet 的输入是控制图，通常是 OpenPose、Depth、Lineart、Canny、Scribble、Seg 这类图片或图片张量。它适合锁定已有视觉结构，适合参考图、草图、已选候选图、用户上传图或工作台画布，不适合直接消化纯文字设计稿。后续调研要关注成熟项目怎样把控制图接入画布、参考图和二轮精修，而不是把 ControlNet 包装成从文本自动生成结构的万能模块。

第四，参考图和角色一致性怎么做。OpenWaifu-Agent 的角色内容生产很依赖人物一致性。要研究 IP-Adapter、LoRA、收藏图参考库、角色样本管理在工程上如何进入生图流程。这里的关键不是单次多加一张参考图，而是让好图、收藏图、角色资产和生成记录能长期复用。

第五，高清导出和最终修复怎么组织。要搞清楚成熟项目里如何区分候选图、精修图、局部修复图和最终导出图；高清阶段如何避免构图漂移和细节崩坏；Real-ESRGAN、ComfyUI upscale、tiled decode、局部 detailer 分别适合什么场景。

## 调研对象

### ComfyUI

仓库：[Comfy-Org/ComfyUI](https://github.com/Comfy-Org/ComfyUI)。截至 2026-04-30 通过 GitHub API 查询约 110k stars。

调研它的原因是 OpenWaifu-Agent 已经以 ComfyUI 作为执行底座。需要深入看它的 workflow API、图生图节点、inpaint 节点、ControlNet 节点、输入图上传接口、history 输出结构和节点式 profile 管理方式。目标是把项目现有单一 workflow 升级成多个明确执行模式：文生图探索、图生图精修、局部修复、高清导出、参考图控制。

### Krita AI Diffusion

仓库：[Acly/krita-ai-diffusion](https://github.com/Acly/krita-ai-diffusion)。截至 2026-04-30 约 10k stars。

这是最贴近创作者工作方式的对象。它把 AI 生图放进 Krita 画布，重点是选区、图层、局部重绘、扩图、参考图和控制层。调研重点是产品交互：用户怎样在画布上表达“改这里”、怎样保留已有成果、怎样把一次生成结果继续加工。它能帮助判断 OpenWaifu 的工作台应该怎样支持图像后处理，而不是把每次任务都当成重新开始。

### InvokeAI

仓库：[invoke-ai/InvokeAI](https://github.com/invoke-ai/InvokeAI)。截至 2026-04-30 约 27k stars。

调研它的重点是创作系统的资产管理、画布、图库、工作流复用和节点编排。OpenWaifu 已经有 run artifact，但现在 artifact 更像日志和结果归档。InvokeAI 这类系统更强调“生成结果可以回到编辑过程”。需要看它怎样管理图像、prompt、参数、mask、历史和再次编辑入口。

### IOPaint

仓库：[Sanster/IOPaint](https://github.com/Sanster/IOPaint)。截至 2026-04-30 约 23k stars。

这是局部修复和扩图方向的重点对象。它的价值在于把“擦除、替换、扩图、用文字描述修改局部”做成独立工具。调研重点是 mask 输入、修复模型选择、结果对比、局部编辑边界和服务接口。OpenWaifu 后续做“修手、修脸、修服装、去掉错误物体”时，应该参考这类架构。

### ControlNet 体系

仓库包括 [lllyasviel/ControlNet](https://github.com/lllyasviel/ControlNet)、[Mikubill/sd-webui-controlnet](https://github.com/Mikubill/sd-webui-controlnet)、[Fannovel16/comfyui_controlnet_aux](https://github.com/Fannovel16/comfyui_controlnet_aux)。截至 2026-04-30，ControlNet 约 34k stars，sd-webui-controlnet 约 18k stars，comfyui_controlnet_aux 约 4k stars。

调研重点是控制图怎样生成、怎样进入 workflow、多个控制条件怎样组合、控制强度和作用区间怎样设置，以及哪些控制图适合二次元插画。这里要特别关注失败边界：控制图质量差会把错误结构稳定下来，多个控制条件冲突会降低画面自然度，模型体系不匹配会导致效果不可用。

### IP-Adapter 与参考图控制

仓库：[cubiq/ComfyUI_IPAdapter_plus](https://github.com/cubiq/ComfyUI_IPAdapter_plus)。截至 2026-04-30 约 5.9k stars。

调研重点是参考图如何影响生成结果。OpenWaifu 的角色一致性、收藏图复用和用户上传参考图都需要这类能力。要搞清楚它适合保留角色气质、画风、脸部印象、服装印象，还是能承担更精确的结构控制。这个结论会影响角色资产系统和收藏图功能的设计。

### 自动检测、局部细化与高清修复

仓库包括 [Bing-su/adetailer](https://github.com/Bing-su/adetailer)、[ltdrdata/ComfyUI-Impact-Pack](https://github.com/ltdrdata/ComfyUI-Impact-Pack)、[geekyutao/Inpaint-Anything](https://github.com/geekyutao/Inpaint-Anything)、[open-mmlab/PowerPaint](https://github.com/open-mmlab/PowerPaint)、[TencentARC/BrushNet](https://github.com/TencentARC/BrushNet)、[xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN)。

这组对象用于回答“图已经大体不错，局部怎么修，最后怎么导出”。ADetailer 和 Impact Pack 关注自动检测、mask 和 detailer；Inpaint Anything 关注分割与修补；PowerPaint 和 BrushNet 关注更强的文本引导修复；Real-ESRGAN 关注最终放大和图像修复。它们能共同决定 OpenWaifu 的后处理路线。

## 调研过程中的分析和碰壁

第一个碰壁点是把 ControlNet 误当成纯文字到结构的桥。深入看 ComfyUI 和 ControlNet 后，结论已经收敛：ControlNet 消费的是图像控制条件。纯文字设计稿需要先产生可见图像、草图、参考图或用户选中的候选图，才能进入 ControlNet 结构控制。继续试图让 ControlNet直接理解设计稿，会把问题带偏。

第二个碰壁点是“先生成候选图，再提控制图，再二轮生成”容易被过度拔高。这个流程的价值是探索后收敛：第一轮找到方向，第二轮保形、精修、高清。它不会让模型凭空获得更强理解力，也可能把第一轮错误结构固定下来。因此它只能在候选图已经被用户或系统认可后使用，不能作为质量提升的核心解释。

第三个碰壁点是姿势模板和程序化骨架路线。把开放动作拆成规则、关节约束、相机参数和场景块，容易退化成状态机。它适合做少量产品快捷入口或可编辑辅助层，不适合作为开放文本生图的主路线。当前更合理的方向是让基座模型承担自由探索，让局部修复、参考图控制、ControlNet 和高清流程承担选中图之后的可控加工。

第四个碰壁点是普通图生图的能力边界。输入图加 prompt 能让结果整体变化，但对细节结构的精确修改不够可靠。成熟工具通常把问题缩小到局部：用户选择区域，系统生成或接收 mask，inpaint 模型只处理指定范围，再用检测器、分割器和对比预览帮助用户判断是否接受。这说明 OpenWaifu 后续必须把“局部修复”做成正式执行模式。

第五个碰壁点是当前项目资源不足。ComfyUI 节点能力存在，但 ControlNet、LoRA、upscale 等模型库存还没有配齐。文档和计划可以先定义接口和执行模式，真正落地时需要按模式补模型、补 workflow、补工作台入口和验收样例。

## 当前推荐收敛方向

OpenWaifu-Agent 的生图层应分成四种清晰模式。第一种是文生图探索，用设计稿和 prompt 生成候选图。第二种是图生图精修，用用户选中图或收藏图作为输入，对整体画面继续加工。第三种是局部修复，用 mask 和 inpaint 处理手、脸、衣服、道具、错误物体和局部瑕疵。第四种是高清导出，把确认后的结果放大、修复并按发布平台规格输出。

ControlNet、IP-Adapter、检测器、分割器、upscaler 都应该作为这些模式里的可选能力接入。这样权责清晰：文生图探索负责打开方向，图生图精修负责延续方向，局部修复负责处理局部问题，高清导出负责形成完成稿。工作台需要围绕这四种模式组织操作入口、预览、artifact 和复跑能力。

下一步调研应先深入 Krita AI Diffusion、InvokeAI 和 IOPaint，确认成熟工具如何把画布、mask、输入图、输出图和历史记录串起来。随后再看 ComfyUI 的具体节点图如何表达同样流程，最后映射回 OpenWaifu 的 execution profile、workflow 模板、runtime artifact 和工作台接口。
