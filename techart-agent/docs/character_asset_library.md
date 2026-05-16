# 角色资产库

角色资产库在 `techart-agent` 中是 Character Tech-Art Kit。它保存一个角色进入本地模型工作流前需要的技术美术起点：文字设定、设定图、三视图、细节特写、姿态动作、服装配饰、模型资源、控制图、审图反馈和可复用样例。

这个资产库的目标是稳定、全面、可延展。稳定意味着同一角色在立绘、事件 CG、表情差分和服装差分中保持识别度。全面意味着角色本体、服装、配饰、姿态、细节和模型资源都能被追溯。可延展意味着角色可以从少量资产开始，逐步加入 LoRA、ControlNet 控制图、局部修复样例和训练数据。

## 总体结构

```text
characters/<character_id>/
  character.json

  identity/
    profile.md
    visual_brief.md
    body_language.md
    color_brief.md

  model_sheets/
    manifest.json
    images/

  detail_sheets/
    manifest.json
    images/

  pose_sheets/
    manifest.json
    images/

  outfits/
    <outfit_id>/
      outfit.json
      manifest.json
      images/

  accessories/
    <accessory_id>/
      accessory.json
      manifest.json
      images/

  model_resources/
    manifest.json
    loras/
    adapters/
    control_models/

  reference_sets/
    candidate_simple.json
    candidate_controlled.json
    refine_selected.json
    inpaint_region.json
    export_upscale.json

  quality/
    checklist.json
    drift_map.json
    approved_examples/
    rejected_examples/
    review_history.jsonl
```

`character.json` 是角色入口，只保存角色 ID、显示名、状态、默认 reference set 和可用资产包。具体内容进入各个资产包。

## identity

`identity` 保存文字形式的基本设定。这里的内容由项目负责人维护，系统只读取和引用。

`profile.md` 保存身份、性格、角色定位和世界观关系。

`visual_brief.md` 保存外观总述：脸部印象、发型体块、体型比例、识别点、整体气质。

`body_language.md` 保存角色身体语言：常见站姿、坐姿、小动作、视线习惯、情绪表达方式。

`color_brief.md` 保存角色主色、辅助色、常见明暗关系和颜色边界。

本地工作流使用这些文本作为 prompt 变量。Prompt 正文由项目负责人维护，工作流只填入受控变量。

## model_sheets

`model_sheets` 保存角色标准设定图。它对应二次元角色生产中的正面、侧面、背面、三分之二视角、表情表。

推荐内容：

- 正脸标准图
- 三分之二脸
- 正面全身
- 侧面全身
- 背面全身
- 表情表
- 角色比例说明图

`manifest.json` 记录每张图的用途：

```json
{
  "schemaVersion": 1,
  "items": [
    {
      "id": "turnaround_front",
      "path": "images/turnaround_front.png",
      "kind": "turnaround",
      "usage": ["body_ratio", "silhouette", "hair_mass"],
      "priority": 100,
      "descriptionZh": "正面标准设定图，用于保持身体比例、头身关系、发型体块和整体轮廓。"
    }
  ]
}
```

候选图工作流读取正脸、三分之二脸和三视图。精修工作流读取更少、更精确的身份图。局部修复工作流只在修脸、头发或身体比例时读取相关图。

## detail_sheets

`detail_sheets` 保存角色局部细节。二次元角色的识别度经常来自细节锚点，局部参考能减少模型在细节上漂移。

推荐内容：

- 眼睛特写
- 刘海和侧发特写
- 后发和发尾特写
- 手部设定
- 腿部或鞋袜细节
- 纹样特写
- 专属配饰细节
- 特殊身体标记

示例：

```json
{
  "id": "eye_detail",
  "path": "images/eye_detail.png",
  "kind": "detail_closeup",
  "usage": ["eye_shape", "iris_design", "face_identity"],
  "priority": 90,
  "descriptionZh": "眼睛特写，用于保持瞳孔形状、眼神气质和眼部配色。"
}
```

细节设定在候选阶段只少量使用。精修和局部修复阶段会更频繁调用它，因为这些阶段处理的是脸、手、发饰、衣领、纹样和道具边缘。

## pose_sheets

`pose_sheets` 保存姿态和动作参考。它提供身体重心、动作趋势、镜头关系和角色身体语言。

推荐内容：

- 中性站姿
- 半身对话姿态
- 坐姿
- 回头
- 奔跑
- 伸手
- 抱物
- 紧张或害羞姿态
- 战斗或特殊动作姿态

姿态图进入本地工作流时有两种用途。第一种是参考图，帮助模型理解动作气质。第二种是控制图来源，工作流可以从姿态参考提取 OpenPose、线稿或轮廓图，再交给 ControlNet 类节点使用。

文字姿态适合候选阶段。精确姿态需要姿态图、草图、线稿或从候选图提取出的控制图。

## outfits

`outfits` 保存角色服装。每套服装独立成包，角色本体和服装分层维护。

推荐内容：

```text
outfits/<outfit_id>/
  outfit.json
  manifest.json
  images/
    front.png
    side.png
    back.png
    collar_detail.png
    sleeve_detail.png
    shoes_detail.png
```

`outfit.json` 保存服装名、使用场景、衣物层级、材质说明、默认配饰和状态。

`manifest.json` 保存服装图用途：

- `outfit_front`
- `outfit_side`
- `outfit_back`
- `collar_detail`
- `sleeve_detail`
- `pattern_detail`
- `shoe_detail`

候选工作流读取服装正面、侧面和关键细节。精修工作流读取本次问题相关的服装图。局部修复衣领、袖口、鞋袜、纹样时，会调用对应细节图。

## accessories

`accessories` 保存长期识别配饰。发饰、眼镜、角色专属挂件、武器、特殊符号都适合独立管理。

配饰包保存：

- 配饰说明
- 佩戴位置
- 正面、侧面和细节图
- 与服装的绑定关系
- 常见漂移问题

配饰在本地工作流中通常作为 detail anchor。候选图阶段可以只传关键配饰，局部修复阶段传高优先级配饰特写。

## model_resources

`model_resources` 保存角色相关的本地模型资源。

推荐内容：

- 角色 LoRA
- 风格 LoRA
- IP-Adapter / 参考图适配资源
- ControlNet 模型需求
- Inpaint 模型需求
- Upscale 模型需求
- 模型 hash、版本、触发词和推荐权重

示例：

```json
{
  "schemaVersion": 1,
  "resources": [
    {
      "id": "character_lora_v1",
      "kind": "lora",
      "path": "loras/character_lora_v1.safetensors",
      "trigger": "character_token",
      "recommendedWeight": 0.75,
      "baseModel": "sdxl",
      "status": "approved"
    }
  ]
}
```

LoRA 负责长期角色一致性。参考图适配负责短期身份约束。ControlNet 负责姿态、线稿、深度、构图等空间约束。Inpaint 模型负责局部修复。Upscale 模型负责最终交付。

## reference_sets

`reference_sets` 是角色资产库与工作流之间的调度层。角色资产可以很多，每次运行只取与当前工作流相关的部分。

事件 CG 候选可以读取：

- 面部身份图
- 三视图或全身比例图
- 本次服装图
- 姿态参考
- 项目画风参考
- 已通过样例

立绘候选可以读取：

- 正脸标准图
- 全身正面图
- 本次服装正面图
- 表情参考
- 透明背景规格

精修可以读取：

- 选中候选图
- 正脸身份图
- 本次服装关键图
- 局部细节锚点

局部修复可以读取：

- 源图
- 遮罩
- 修复区域对应细节图
- 必要的面部身份图或服装图

高清导出可以读取：

- 通过验收图
- 项目导出规格
- 画风参考
- upscale 配置

具体绑定由 `config/workflow_asset_bindings.json` 管理，资产角色由 `config/reference_roles.json` 管理。

## quality

`quality` 保存角色质量标准和反馈数据。

`checklist.json` 保存每次审图要检查的内容：

- 脸型是否符合角色标准
- 发型体块是否符合设定图
- 核心配饰是否保留
- 体型比例是否稳定
- 指定服装是否正确
- 姿态动作是否符合任务
- 画风是否符合项目美术标准

`drift_map.json` 保存常见漂移与修复时应调用的资产：

```json
{
  "knownDrifts": [
    {
      "issue": "face_drift",
      "descriptionZh": "脸部气质偏离角色标准。",
      "useWhenFixing": ["face_front", "face_3q", "approved_face_example"]
    },
    {
      "issue": "outfit_detail_loss",
      "descriptionZh": "服装细节或配饰丢失。",
      "useWhenFixing": ["outfit_front", "accessory_detail"]
    }
  ]
}
```

`approved_examples` 保存通过验收的图。`rejected_examples` 保存弃用图和失败原因。`review_history.jsonl` 保存审图历史。后续训练 LoRA、调整参考图选择规则和改进工作流，都依赖这些数据。

## 最小启动集

第一版角色只需要这些资产：

```text
character.json
identity/visual_brief.md
model_sheets/manifest.json
model_sheets/images/
outfits/<outfit_id>/outfit.json
outfits/<outfit_id>/manifest.json
outfits/<outfit_id>/images/
reference_sets/candidate_simple.json
quality/checklist.json
```

这套最小集可以支持本地候选图生成。后续逐步加入 `detail_sheets`、`pose_sheets`、`model_resources`、`quality/approved_examples` 和 `quality/rejected_examples`。
