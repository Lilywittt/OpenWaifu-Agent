# 多模态生图能力改进计划

## 核心判断

OpenWaifu-Agent 现在已经证明了 Agent 编排、工作台交互、ComfyUI 自动化执行、运行记录和发布流程。面向网易雷火智能体研发工程师（多模态方向），下一阶段要把项目从“角色内容生产 Agent”推进到“能支持游戏美术和 UGC 的生图工具”。关键变化是：用户能获得更可控、更一致、更适合继续修改的图像结果；系统也能把用户认可的好结果保存下来，服务后续出图、审图和训练。

收藏功能应该进入这条路线。用户收藏一张图，含义很直接：这张图值得保留。系统需要记录它从哪里来、用什么 prompt 和 workflow 生成、为什么被喜欢、还能不能继续用于训练或参考。短期内，收藏图可以帮助筛选候选图、比较不同工作流、挑选 LoRA 数据候选和建立参考图库；样本足够后，再考虑做轻量排序模型或偏好模型实验。收藏图进入训练前还要补充来源、生成参数、角色设定、图像缺陷、用途判断和使用边界。

本计划以五个补强点为主线：

1. 复杂 ComfyUI 工作流
2. LoRA 最小训练流程
3. 图像级质量评估 artifact
4. 训练数据与打标自动化
5. Diffusers 最小推理脚本

## 改进目标

这次改进要把生图从“能出一张图”推进到“能稳定做出可继续加工的图”。用户在工作台里应该能看到候选图、精修图、局部修复图、高清导出图和质量判断。项目维护者也应该能知道：哪些输入更容易出好图，哪个工作流更稳定，哪个模型或 LoRA 更适合当前角色。

具体要完成五件事。

第一件事是分层出图。快速模式服务体验和灵感预览，精修模式服务高质量完成稿。用户先用较低成本确认方向，再把值得继续加工的图送入精修流程。这样可以减少无效等待，把算力花在有价值的候选图上。

第二件事是保存角色材料。当前角色一致性主要依赖角色设定和提示词，下一步要把优秀角色样本整理成 LoRA 数据候选和参考图库。用户反复生成同一个角色时，系统应该越来越稳定地保留发型、脸型、服装记忆点和整体气质。

第三件事是记录图像质量。工作台需要让用户表达“这张图好在哪里、差在哪里、能不能继续用”。收藏表示喜欢，评分和标签说明原因。系统积累这些记录后，可以比较不同工作流、不同提示词策略和不同模型的真实表现。

第四件事是整理数据集。被认可的图片、对应 prompt、生成参数、运行记录、评分和缺陷标签要能导出。这个数据集可以服务 LoRA 训练、参考图筛选、候选图排序和后续评估。

第五件事是补底层验证。ComfyUI 继续承担主工作流，Diffusers 脚本用于参数实验、LoRA 验证和批量推理。这样项目既保留节点式工作流的便利，也能证明自己理解扩散模型推理过程。

## 五个补强点分别解决什么问题

复杂 ComfyUI 工作流解决的是出图质量和可接管问题。简单版让用户快速看方向，复杂版把一个方向继续打磨成可发布、可继续编辑、可归档的完成稿。

LoRA 训练流程解决的是角色一致性问题。角色内容和游戏美术都需要稳定的人物特征。跑通 LoRA 后，系统可以围绕一个角色长期积累图像样本、验证集和模型版本，让角色生产更稳定。

图像级质量评估解决的是“只凭感觉审图”的问题。用户收藏、评分和缺陷标签可以告诉系统：这张图角色像不像，构图是否合适，手脸有没有问题，是否适合发布，是否适合训练。

训练数据与打标自动化解决的是素材散乱问题。人工挑图很容易散落在文件夹里，自动化工具要负责整理图片、生成 caption、记录来源、筛掉不合格样本、输出训练配置和验证 prompt。

Diffusers 最小推理脚本解决的是底层实验问题。它可以快速验证 LoRA、scheduler、CFG、denoise、seed 和 batch 结果，帮助判断一个策略是否值得进入 ComfyUI 正式工作流。

## 收藏数据怎么用

收藏功能的定位应升级为“好图入口”。用户在工作台里收藏一张图，系统要保存它的来源、角色、场景、prompt、workflow、模型参数、最终图片和收藏时间。下一步增加评价后，用户还可以标记它适合发布、适合做参考图、适合进入训练候选，或需要先做局部修复。

收藏数据分三步使用。

第一步，收藏帮助筛选候选图。同一次任务生成多张候选时，用户收藏的图就是 chosen sample，同组未收藏图可以作为弱 rejected sample。系统据此知道哪种构图、姿态、提示词和 seed 更容易被认可。

第二步，收藏帮助评估工作流。simple 和 complex 都运行一段时间后，可以统计哪个 preset 更容易产出收藏图，哪个更容易出现手脸问题，哪个耗时更高但收藏率更好。这个统计比单次主观判断更适合指导后续迭代。

第三步，收藏帮助积累训练候选。收藏图经过二次审查后，进入 LoRA 数据候选或参考图库。训练集只接收 `trainable=true` 的样本；带缺陷但构图好的图可以进入参考图库或局部修复队列。这样既利用了用户偏好，又能控制训练数据质量。

最终目标是让用户每一次审图都为系统提供反馈。好图进入偏好库，优秀且干净的图进入训练候选，有缺陷但方向好的图进入精修队列，失败图进入问题统计。系统用这些记录判断下一步该保留什么、修复什么、训练什么。

## 开发路线

第一阶段先做工作流切换。用户能选择快速出图或精修工作流，系统记录每次使用的 preset、workflow、耗时和结果。这个阶段的验收标准是：快速模式稳定，精修模式能在测试工作台跑通，并且结果可回看。

第二阶段做候选图和评价。工作台展示候选图，用户可以收藏、评分、打缺陷标签、标记用途。这个阶段的验收标准是：收藏图能追溯到 run、prompt、workflow 和评价记录。

第三阶段做 LoRA 数据候选。系统从收藏和人工素材中导出角色数据集，生成 caption、训练配置、验证 prompt 和拒绝样本报告。这个阶段的验收标准是：能跑通一个小规模角色 LoRA，并在工作台里用固定验证样例展示效果变化。

第四阶段做偏好数据集。系统把收藏、评分和同组候选关系导出为 preference dataset，用于 A/B 报告、候选图排序和后续偏好模型实验。这个阶段的验收标准是：能回答哪些工作流、哪些参数、哪些 prompt 策略更容易产出好图。

第五阶段做底层实验工具。Diffusers 脚本用于快速验证 LoRA、图生图参数和批量生成结果。这个阶段的验收标准是：能用脚本复现关键实验，并把有效策略迁回 ComfyUI 工作流。

## 技术实施说明

下面的技术设计用于支撑上述功能。实施时先保证现有工作台和公网体验稳定，再逐步开放高成本功能。

## 当前基线

已有执行层位于 `src/execution/`。当前 `run_execution_pipeline` 会读取 active profile，加载 workflow 模板，注入 checkpoint、正向提示词、负向提示词、尺寸、seed、sampler 参数，提交 ComfyUI，轮询 history，下载第一张输出图，并写出：

```text
runtime/runs/<run_id>/execution/
  00_execution_input.json
  01_workflow_request.json
  02_submit_response.json
  03_workflow_history.json
  04_execution_package.json
```

当前 profile 位于 `config/execution/comfyui_local_animagine_xl.json`，workflow 位于 `config/workflows/comfyui/animagine_xl_basic.workflow.json`。这是一条基础文生图流程，适合验证端到端执行，但还没有候选图、图生图、局部修复、高清导出、LoRA 接入和图像级评估。

已有收藏功能位于 `src/review_favorites.py` 和 `src/workbench/store.py`。收藏索引写入：

```text
runtime/service_state/shared/review_favorites.jsonl
```

收藏记录当前能保存 run、路径、标题、来源、阶段、场景标题和 run root。这个结构足够作为偏好数据入口，但还需要补充图像级评价、候选图上下文、同组负样本、导出工具和数据集 manifest。

## 总体架构

新增功能应复用现有执行层和工作台，不另起并行系统。推荐目标结构如下：

```text
config/
  execution/
    presets.json
    profiles/
      comfyui_animagine_xl_simple_v1.json
      comfyui_animagine_xl_complex_v1.json
      comfyui_animagine_xl_complex_v2.json
  workflows/
    comfyui/
      simple/
        animagine_xl_simple_v1.workflow.json
      complex/
        animagine_xl_complex_v1.workflow.json
        animagine_xl_complex_v2.workflow.json
  datasets/
    lora_character_dataset_v1.json
    preference_dataset_v1.json

src/
  execution/
    presets.py
    artifacts.py
    candidate_manifest.py
  image_quality/
    review_schema.py
    image_evaluator.py
    preference_export.py
  datasets/
    image_inventory.py
    captioning.py
    lora_dataset_builder.py
    preference_dataset_builder.py

tools/
  comfyui/
    audit_resources.py
    smoke_workflow.py
    batch_ab_eval.py
  datasets/
    build_lora_dataset.py
    build_preference_dataset.py
    validate_dataset.py
  diffusers/
    run_txt2img.py
    run_img2img.py
    run_batch.py

runtime/
  runs/<run_id>/
    execution/
    evaluation/
    dataset_exports/
  datasets/
    lora/<dataset_id>/
    preference/<dataset_id>/
```

`config` 保存可审阅配置和 workflow 模板，`src` 保存可复用代码，`tools` 保存人工运行的维护与实验工具，`runtime` 保存生成物、数据集导出和实验报告。训练图片、模型权重、临时数据和导出样本都进入 `runtime/` 或 `.local/`，不进入 Git。

## 一、复杂 ComfyUI 工作流

### 目标

把基础文生图执行层升级为可切换工作流。公网体验继续走快速稳定的 simple preset，高权限测试工作台可以选择 complex preset。复杂工作流逐步覆盖构图控制、候选图、图生图细化、局部修复和高清导出。

### 设计

执行请求增加 `executionPreset` 字段：

```json
{
  "executionPreset": "simple"
}
```

合法值先定义为：

```text
simple
complex
```

`simple` 映射到快速文生图 profile，`complex` 先映射到 `complex_v1`，后续成熟后可在 `presets.json` 中切换到 `complex_v2`。公网工作台默认 simple，高权限测试工作台显示模式选择。复跑、历史记录、run summary 和 execution package 都要记录 preset、profileId、workflowId、workflowVersion。

推荐 `presets.json`：

```json
{
  "defaultPreset": "simple",
  "presets": {
    "simple": {
      "label": "快速出图",
      "profilePath": "config/execution/profiles/comfyui_animagine_xl_simple_v1.json",
      "publicEnabled": true
    },
    "complex": {
      "label": "精修工作流",
      "profilePath": "config/execution/profiles/comfyui_animagine_xl_complex_v1.json",
      "publicEnabled": false
    }
  }
}
```

`simple_v1` 保持低风险：checkpoint、正负提示词、KSampler、VAE decode、ImageScale、SaveImage。它承担公网体验、回归基线和发布图规格输出。

`complex_v1` 使用现有节点优先落地：base pass 生成构图和主体，latent upscale 承接细节，refine pass 低 denoise 精修，VAEDecodeTiled 降低显存压力，ImageScale 输出平台规格。这个阶段先解决“单次采样直接作为最终图”的问题。

`complex_v2` 引入外部资源：ControlNet / OpenPose / Depth / Lineart、IP-Adapter 或参考图机制、角色 LoRA、Detailer、Upscale model。它面向高权限工作台和批量审图，成熟后再考虑公网开放。

### Artifact 契约

复杂工作流要保存候选和阶段记录。建议新增：

```text
runtime/runs/<run_id>/execution/
  05_candidate_manifest.json
  candidates/
    candidate_001.png
    candidate_002.png
  refine/
    selected_candidate.png
    img2img_refine.png
  inpaint/
    face_fix.png
    hand_fix.png
  export/
    final_1080x1350.png
    final_source_size.png
```

`05_candidate_manifest.json` 示例：

```json
{
  "runId": "2026-xx-xx_xxx",
  "executionPreset": "complex",
  "workflowId": "animagine_xl_complex_v1",
  "candidates": [
    {
      "candidateId": "candidate_001",
      "imagePath": "execution/candidates/candidate_001.png",
      "seed": 123,
      "stage": "base",
      "selected": true,
      "selectionReason": "人工选择或自动评分最高"
    }
  ],
  "finalImagePath": "execution/export/final_1080x1350.png"
}
```

### 开发步骤

第一步增加 preset 解析，但默认仍走现有 active profile。完成后不改变现有产品行为。

第二步把当前基础 workflow 移入 simple profile，保持输出一致。跑一次 smoke，确认原有工作台、生图和发布层不受影响。

第三步实现 complex_v1 profile 和 workflow。先只接内置节点，减少安装成本。高权限工作台增加模式选择，公网入口固定 simple。

第四步增加候选图 manifest。即使 complex_v1 初期只输出一张图，也要先写入 manifest，给后续 batch candidates、收藏和图像评估留出稳定契约。

第五步实现 batch A/B 工具。选择固定 prompt package，分别跑 simple 和 complex，输出耗时、失败率、尺寸、图片网格和人工评分表。

### 验收标准

simple 与当前执行层输出路径和 run summary 兼容。complex 能在高权限工作台选择并完成一次真实运行。`04_execution_package.json` 记录 preset、profile、workflow。`05_candidate_manifest.json` 至少记录最终图。A/B 工具能生成可审阅报告。公网体验不暴露未成熟 complex。

## 二、LoRA 最小训练流程

### 目标

把角色一致性从 prompt 控制推进到 LoRA 控制。第一阶段做一个小规模角色 LoRA，从素材准备、caption、训练配置、验证 prompt、效果对比到 ComfyUI 接入完整跑通。

### 数据来源

LoRA 数据候选有三类：

1. 人工整理的角色基准图
2. 已收藏的高质量生成图
3. 已发布或人工确认可继续使用的最终图

收藏图片可以进入候选池，但进入训练集前必须通过二次筛选。收藏只代表“这张图值得保留”，还不代表“这张图适合训练”。训练样本需要满足角色特征清楚、没有明显肢体错误、没有水印乱码、画风不偏离目标、分辨率足够、可追溯到生成参数。

### 数据集结构

推荐导出到 runtime：

```text
runtime/datasets/lora/<dataset_id>/
  images/
    000001.png
    000001.txt
    000002.png
    000002.txt
  manifests/
    dataset_manifest.json
    source_favorites.jsonl
    rejected_samples.jsonl
  validation/
    validation_prompts.json
    baseline_outputs/
    lora_outputs/
  train/
    train_config.toml
    run_train.ps1
```

`dataset_manifest.json` 示例：

```json
{
  "datasetId": "role_lora_single_xiaoyi_v1",
  "createdAt": "2026-xx-xxTxx:xx:xx",
  "characterId": "single_xiaoyi",
  "sources": ["manual_assets", "review_favorites"],
  "sampleCount": 36,
  "captionPolicy": "character_core_tags_first",
  "licensePolicy": "local_private_research",
  "samples": [
    {
      "sampleId": "000001",
      "imagePath": "images/000001.png",
      "captionPath": "images/000001.txt",
      "sourceRunId": "2026-xx-xx_xxx",
      "sourceFavoriteKey": "run:2026-xx-xx_xxx",
      "qualityTags": ["character-clear", "no-major-defect"],
      "rejected": false
    }
  ]
}
```

### 收藏如何进入 LoRA

收藏功能保留当前轻量入口。新增 `build_lora_dataset.py` 从 `review_favorites.jsonl` 读取收藏，再解析 run detail、生成图路径、prompt package、Prompt Guard 报告和 run summary。导出时给每张图一个处理状态：

```text
candidate
accepted
rejected
needs_crop
needs_caption_review
```

工作台后续可以给收藏加评价维度：

```text
角色一致性
画面完成度
局部缺陷
适合训练
适合发布
适合做参考图
```

第一阶段先不强制 UI 改造。可以由导出工具生成 `needs_review` 列表，人工在文件里筛选。等流程稳定后，再把这些字段加回工作台。

### 训练接入

训练工具可以先对接本地常用 LoRA 训练方案，如 kohya、sd-scripts 或其他现有训练环境。OpenWaifu-Agent 不直接吞掉训练框架，只负责数据集准备、配置生成、训练命令包装、验证 prompt 和结果归档。

训练完成后登记模型：

```text
runtime/model_registry/lora/
  role_lora_single_xiaoyi_v1.json
```

登记字段：

```json
{
  "modelId": "role_lora_single_xiaoyi_v1",
  "modelPath": ".local/ComfyUI/models/loras/role_lora_single_xiaoyi_v1.safetensors",
  "baseCheckpoint": "animagine-xl-4.0-opt.safetensors",
  "triggerWords": ["single xiaoyi"],
  "datasetId": "role_lora_single_xiaoyi_v1",
  "validationReportPath": "runtime/datasets/lora/.../validation/report.json"
}
```

ComfyUI profile 增加可选 LoRA 节点绑定。执行请求允许传入 `loraModelId`，默认值为空。Prompt Builder 负责角色描述和触发词策略，执行层负责把 LoRA 模型接入 workflow。

### 验收标准

能从收藏和人工素材导出一个训练数据集。能生成 caption 和训练配置。能跑通一次小规模 LoRA。能用固定验证 prompt 对比 baseline 和 LoRA 输出。能在 ComfyUI workflow 中加载 LoRA 并生成图片。所有训练产物和模型权重不进入 Git。

## 三、图像级质量评估 Artifact

### 目标

把“好不好”从主观印象转为可记录、可对比、可导出的质量信号。Prompt Guard 继续负责文本和提示词逻辑，图像级评估负责最终图片和候选图质量。

### 评价维度

第一版使用人工结构化评价，维度固定为：

```text
角色一致性
构图匹配度
动作姿态
脸部质量
手部质量
服装与配饰
背景与文字
整体完成度
继续精修价值
适合发布
适合训练
```

评分用 1 到 5。缺陷用标签记录：

```text
bad_hands
bad_face
extra_limb
wrong_character_feature
outfit_drift
messy_background
watermark_or_text
over_sharpened
low_detail
composition_mismatch
```

### Artifact 结构

每个 run 增加：

```text
runtime/runs/<run_id>/evaluation/
  00_image_review.json
  01_candidate_scores.jsonl
  02_preference_signal.json
```

`00_image_review.json` 示例：

```json
{
  "runId": "2026-xx-xx_xxx",
  "imagePath": "output/xxx.png",
  "reviewedAt": "2026-xx-xxTxx:xx:xx",
  "reviewer": "local_user",
  "scores": {
    "characterConsistency": 4,
    "compositionMatch": 5,
    "pose": 4,
    "face": 4,
    "hands": 3,
    "outfit": 5,
    "background": 4,
    "overall": 4,
    "refinePotential": 5
  },
  "labels": ["bad_hands"],
  "decisions": {
    "favorite": true,
    "publishable": true,
    "trainable": false,
    "referenceCandidate": true
  },
  "notes": "手部需要修复，但构图和角色状态很好。"
}
```

`02_preference_signal.json` 用于统一收藏和评分：

```json
{
  "runId": "2026-xx-xx_xxx",
  "imagePath": "output/xxx.png",
  "positiveSignal": true,
  "signalSources": ["favorite", "manual_score"],
  "overallScore": 4,
  "trainable": false,
  "referenceCandidate": true,
  "sameRequestNegativeCandidates": [
    "candidate_002",
    "candidate_003"
  ]
}
```

### 收藏融合方式

收藏是正向信号。新增评价后，收藏可以自动写入 `positiveSignal=true`，但训练用途由 `trainable` 字段单独决定。这样一个图可以同时是“喜欢的图”“适合发布的图”“适合做参考图”，也可以因为局部缺陷而暂时不进入 LoRA 训练集。

对于同一次请求生成的多个候选图，被收藏的候选可以作为正样本，同组未收藏候选可以作为弱负样本。这个结构可以形成偏好对：

```json
{
  "promptContextId": "run_xxx_candidate_group",
  "chosenImagePath": "candidate_001.png",
  "rejectedImagePath": "candidate_003.png",
  "reason": "favorite_over_same_request_candidate"
}
```

偏好对短期用于 A/B 报告和候选图排序规则，样本量足够后再训练轻量 reranker 或偏好模型。

### 自动评估扩展

第二阶段接入自动辅助，人工审阅仍然作为最终判断。可选功能：

1. tagger 提取图像标签，与设计稿和 Prompt Guard 输出对照。
2. VLM 生成图像描述和缺陷检查，输出结构化报告。
3. 姿态检测或人体关键点检测辅助判断动作偏差。
4. CLIP 相似度用于同 prompt 候选粗筛。

自动评估结果写入 `autoReview`，人工最终判断写入 `manualReview`。工作台展示时以人工判断为准，自动结果作为参考。

### 验收标准

工作台能记录图片评分、缺陷标签和用途判断。收藏能转化为 preference signal。候选图能形成 chosen/rejected 偏好对。A/B 工具能按评分输出 simple/complex 对比。导出的 preference dataset 可被后续 reranker 或训练实验读取。

## 四、训练数据与打标自动化

### 目标

建立数据处理和打标工具，覆盖 LoRA 数据准备、收藏样本导出、caption 生成、标签规范检查和训练配置生成。这直接对应岗位里的“数据处理、模型打标、LoRA训练、Comfyui工作流自动生成等自动化小工具”。

### 工具设计

`tools/datasets/build_lora_dataset.py`：

```text
输入：角色素材目录、收藏索引、过滤规则、输出 dataset_id
输出：训练图片、caption、dataset_manifest、rejected_samples、validation_prompts
```

`tools/datasets/build_preference_dataset.py`：

```text
输入：review_favorites.jsonl、run 目录、candidate_manifest、image_review
输出：preference_pairs.jsonl、positive_samples.jsonl、negative_samples.jsonl
```

`tools/datasets/validate_dataset.py`：

```text
检查：图片存在、尺寸合法、caption 存在、路径不越界、重复图、低清图、缺陷标签、manifest 完整性
```

`src/datasets/captioning.py` 先支持半自动策略：

```text
固定角色核心标签 + 从 run artifact 提取场景/服装/动作标签 + 人工可编辑 caption
```

后续再接 tagger 或 VLM 自动 caption。caption 文件必须 UTF-8 保存。

### 数据质量规则

进入 LoRA 训练集的样本必须满足：

```text
图片存在且可打开
长宽达到最低阈值
角色主体清楚
没有明显水印或乱码
没有严重肢体错误
caption 存在且包含角色核心触发词
source run 或 source path 可追溯
```

被拒绝的样本进入 `rejected_samples.jsonl`，记录原因：

```text
missing_file
too_small
duplicate
bad_anatomy
watermark_or_text
character_drift
caption_missing
manual_reject
```

### 收藏数据的训练边界

收藏样本进入三个池：

```text
preference_positive：用于偏好分析和 A/B 报告
reference_candidate：用于 IP-Adapter、参考图、人工审阅
train_candidate：通过二次筛选后进入 LoRA 数据候选
```

这三个池分开能避免把“喜欢”直接当成“适合训练”。好评图片可能构图很好但手部有问题，也可能适合发社媒但不适合训练角色 LoRA。训练数据集必须以 `trainable=true` 为准。

### 验收标准

能从收藏索引导出 preference dataset。能从人工素材和收藏候选生成 LoRA dataset。能输出 rejected samples 和拒绝原因。caption、manifest、训练配置和验证 prompt 都能被版本化记录。导出结果不污染 Git。

## 五、Diffusers 最小推理脚本

### 目标

补齐底层推理理解和批量实验工具。ComfyUI 继续作为主执行引擎，Diffusers 脚本用于验证扩散模型核心参数、LoRA 加载、图生图 denoise、batch 推理和训练验证。

### 脚本范围

`tools/diffusers/run_txt2img.py`：

```text
加载 SDXL / Animagine 兼容 pipeline
支持 prompt、negative prompt、seed、steps、CFG、width、height、scheduler
支持 LoRA 权重加载
保存图片和 params.json
```

`tools/diffusers/run_img2img.py`：

```text
加载输入图
支持 denoise strength
支持 LoRA
保存前后对比和 params.json
```

`tools/diffusers/run_batch.py`：

```text
读取 prompts.jsonl
批量执行 txt2img 或 img2img
输出 batch_report.json
```

### 输出结构

```text
runtime/diffusers_runs/<run_id>/
  inputs/
    prompts.jsonl
  outputs/
    000001.png
    000002.png
  params.json
  batch_report.json
```

### 与主项目关系

Diffusers 脚本不替换 ComfyUI 执行层。它承担三类任务：

1. 面试和技术验证时证明底层理解。
2. LoRA 训练后快速跑验证图。
3. 对 scheduler、CFG、denoise、seed 等参数做批量实验。

当某个 Diffusers 实验稳定产生收益，再考虑把策略迁回 ComfyUI workflow 或新增执行 profile。

### 验收标准

能本地生成一张 txt2img。能基于输入图完成 img2img。能加载 LoRA。能批量读取 prompts.jsonl 并输出报告。显存不足时给出清楚错误和建议参数。

## 收藏数据的后续用途

收藏功能建议分三阶段升级。

第一层是立即可做的偏好索引。保留 `review_favorites.jsonl` 作为用户点击记录，新增导出工具把收藏转为 `preference_positive`。这一层不改工作台 UI，也不改变当前收藏行为。

第二层是可审阅评分。工作台在收藏旁边增加“评价”入口，记录评分、缺陷标签和用途判断。收藏按钮继续表示“我喜欢这张图”，评价表负责说明它为什么好、能用在哪里。

第三层是训练与排序。收藏和评价共同生成 preference dataset。短期用它评估 simple/complex、筛选候选图和选 LoRA 样本；中期训练轻量图像 reranker；长期在样本规模足够时尝试偏好微调或风格 LoRA。这个顺序能保证偏好信号先服务实际产品，再逐步进入模型层。

偏好数据的最小 schema：

```json
{
  "signalId": "pref_2026_xxx",
  "createdAt": "2026-xx-xxTxx:xx:xx",
  "source": "favorite",
  "runId": "2026-xx-xx_xxx",
  "imagePath": "output/xxx.png",
  "promptPackagePath": "prompt_guard/02_prompt_package.json",
  "executionPackagePath": "execution/04_execution_package.json",
  "candidateGroupId": "run_xxx_candidates",
  "positive": true,
  "scores": {
    "overall": 5,
    "characterConsistency": 5,
    "compositionMatch": 4
  },
  "decisions": {
    "publishable": true,
    "trainable": false,
    "referenceCandidate": true
  }
}
```

## 开发计划

### 阶段 0：契约和资源审计

目标是先固定接口和资源现状，避免后面边做边改边界。

交付物：

```text
config/execution/presets.json
tools/comfyui/audit_resources.py
tools/comfyui/smoke_workflow.py
```

工作内容：

1. 审计 ComfyUI 节点、模型目录、checkpoint、LoRA、ControlNet、upscale model。
2. 定义 preset/profile/workflow 的字段契约。
3. smoke 工具检查 profile 绑定、workflow 节点输入、ComfyUI 健康和输出节点。

验收：

smoke 默认 dry-run，不触发真实生图。显式传入 `--submit` 后能提交 simple workflow。公网工作台行为不变化。

### 阶段 1：simple/complex 执行模式

目标是让工作台可以切换生图工作流。

交付物：

```text
src/execution/presets.py
config/execution/profiles/comfyui_animagine_xl_simple_v1.json
config/execution/profiles/comfyui_animagine_xl_complex_v1.json
config/workflows/comfyui/simple/...
config/workflows/comfyui/complex/...
```

工作内容：

1. 当前 profile 迁移为 simple_v1。
2. 增加 complex_v1 workflow。
3. `run_execution_pipeline` 记录 preset/profile/workflow 元信息。
4. 高权限测试工作台增加模式选择。
5. 复跑和历史记录保留 executionPreset。

验收：

simple 跑通现有任务。complex 在本地测试工作台跑通一次。两个模式都写出 execution package。失败时能指出 profile、workflow、节点或 ComfyUI 服务问题。

### 阶段 2：候选图与图像评估

目标是把收藏和审图变成结构化质量数据。

交付物：

```text
src/execution/candidate_manifest.py
src/image_quality/review_schema.py
src/image_quality/preference_export.py
runtime/runs/<run_id>/evaluation/*.json
```

工作内容：

1. 写出 `05_candidate_manifest.json`。
2. 工作台增加图像评价入口。
3. 收藏自动生成 preference signal。
4. 同组候选形成 chosen/rejected 偏好对。
5. `batch_ab_eval.py` 汇总 simple/complex 质量和耗时。

验收：

一张收藏图能追溯到 run、prompt、execution package、图片路径和评价记录。A/B 报告能按整体评分、角色一致性、局部缺陷和耗时排序。收藏列表仍能正常使用。

### 阶段 3：LoRA 数据集和最小训练流程

目标是把角色素材和收藏好图转成可训练数据集。

交付物：

```text
src/datasets/lora_dataset_builder.py
tools/datasets/build_lora_dataset.py
tools/datasets/validate_dataset.py
runtime/datasets/lora/<dataset_id>/
runtime/model_registry/lora/<model_id>.json
```

工作内容：

1. 从人工素材和收藏候选生成 dataset manifest。
2. 生成 caption 和 rejected samples。
3. 生成训练配置和验证 prompt。
4. 跑通一次小规模 LoRA。
5. 将 LoRA 登记到 model registry。
6. complex profile 支持可选 LoRA。

验收：

能用同一组验证 prompt 对比 baseline 和 LoRA 输出。训练配置、数据来源、验证结果可追溯。ComfyUI 能加载 LoRA 生成图。训练权重和数据集不进 Git。

### 阶段 4：训练数据自动化和偏好数据集

目标是把收藏、评分、候选图和训练样本整理成可维护数据。

交付物：

```text
tools/datasets/build_preference_dataset.py
runtime/datasets/preference/<dataset_id>/
```

工作内容：

1. 导出 positive samples。
2. 导出 chosen/rejected pairs。
3. 统计收藏图来源、prompt、workflow、score、缺陷标签。
4. 生成 preference dataset report。
5. 根据偏好数据给 simple/complex、LoRA 版本和 prompt 策略做对比。

验收：

preference dataset 能稳定复现。报告能回答哪些 workflow 更容易产出收藏图，哪些 prompt 或角色场景更容易失败，哪些收藏图适合训练或做参考图。

### 阶段 5：Diffusers 最小脚本和底层验证

目标是补齐底层推理证据，并服务 LoRA 验证和批量实验。

交付物：

```text
tools/diffusers/run_txt2img.py
tools/diffusers/run_img2img.py
tools/diffusers/run_batch.py
```

工作内容：

1. 支持 txt2img。
2. 支持 img2img 和 denoise strength。
3. 支持 LoRA load。
4. 支持 prompts.jsonl 批量执行。
5. 输出 params 和 batch report。

验收：

能生成可复现图片。能解释并展示 CFG、steps、scheduler、denoise、seed 对结果的影响。能用 LoRA 生成验证图。

## 风险和边界

显存是第一风险。本机 6GB 级别显存不适合一开始就堆大量高成本节点。complex_v1 应优先使用 latent upscale、低 denoise refine 和 tiled decode；ControlNet、IP-Adapter、Detailer、高清模型放到 complex_v2。

收藏数据质量是第二风险。收藏代表主观喜欢，训练前还要检查角色一致性、局部缺陷、分辨率、caption 和使用许可。用收藏直接扩充训练集会放大生成图里的错误特征。

工作台复杂度是第三风险。评价、收藏、候选、训练用途都进入 UI 后，界面容易变重。第一阶段用导出工具和 JSON artifact 承接，等数据流程跑通后再把常用动作放进 UI。

目录污染是第四风险。图片、训练数据、模型权重和实验输出必须进入 `runtime/` 或 `.local/`。Git 只记录配置、代码、文档和小型示例 schema。

## 面试表达收束

这套计划可以在面试中这样表达：

> OpenWaifu-Agent 当前最成熟的是 Agent 编排、ComfyUI 自动化执行、工作台交互和运行追踪。下一步我会围绕游戏美术 AIGC 工具链补强五件事：把基础文生图升级成 simple/complex 两套 ComfyUI 工作流；跑通角色 LoRA 的数据、训练、验证和接入流程；把图像质量评估写成 artifact；用收藏好图生成偏好数据和训练候选；补 Diffusers 最小脚本来验证底层推理和 LoRA 效果。收藏功能先服务候选筛选和 A/B 评估，再进入 LoRA 数据筛选和偏好模型实验。
