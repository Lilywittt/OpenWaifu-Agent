# 任务契约

美术任务是产品里的最小生产单元。每个任务都要说明要生成什么图、服务哪个项目、涉及哪些角色、采用哪个工作流、输出到什么规格。

## 通用字段

```json
{
  "schemaVersion": 1,
  "taskId": "task_20260516_001",
  "projectId": "demo_project",
  "assetTypeId": "event_cg",
  "titleZh": "放课后教室事件 CG",
  "status": "draft",
  "characterIds": ["shan_xiaoyi"],
  "workflowPresetId": "candidate_simple",
  "exportPresetId": "event_cg_1920x1080",
  "createdAt": "2026-05-16T00:00:00+08:00",
  "updatedAt": "2026-05-16T00:00:00+08:00"
}
```

## 事件 CG 输入

```json
{
  "sceneBriefZh": "放学后的教室里，角色坐在靠窗座位，夕阳从窗外照进来。",
  "cameraBriefZh": "中景，略低视角，窗边和课桌形成画面层次。",
  "moodZh": "安静、微妙的心动、带一点放课后的疲惫感。",
  "requiredElementsZh": ["窗边座位", "夕阳", "课桌", "书包"],
  "avoidElementsZh": ["拥挤背景", "夸张动作"]
}
```

## 角色立绘输入

```json
{
  "characterId": "shan_xiaoyi",
  "outfitId": "school_uniform_summer",
  "expressionId": "shy_smile",
  "poseBriefZh": "半身正面，双手抱书，视线略微偏向一侧。",
  "backgroundMode": "transparent",
  "requiredElementsZh": ["清晰脸部", "完整上半身", "服装边缘干净"]
}
```

## 状态

任务状态建议先定义为：

```text
draft
queued
running
candidate_ready
selected
refining
needs_review
accepted
exported
archived
failed
```

状态变化要写入任务记录。后续工作台才能可靠显示队列、失败原因、复跑入口和导出结果。
