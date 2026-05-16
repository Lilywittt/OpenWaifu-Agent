# 本地工作流架构

`techart-agent` 采用 Windows 桌面客户端、本地后端、本地项目资产库和本地 ComfyUI 工作流。生产链路依赖本地模型、角色资产、控制图和工作流配置。

## 主链路

```text
创建美术任务
  -> 选择项目、角色、服装、资产类型、事件、姿态和动作
  -> 资产选择器读取角色资产库
  -> 生成本地生产包
  -> ComfyUI 工作流执行
  -> 候选图、精修图、局部修复图或导出图回写任务
  -> 审图、入库、导出、反馈沉淀
```

## 前后端边界

后端负责：

- 读取项目美术标准、角色资产、服装资产和模型资源配置
- 创建任务和任务组
- 根据工作流选择本次运行需要的参考图、控制图和模型资源
- 生成 ComfyUI workflow input
- 提交队列、轮询结果、写入运行记录
- 保存审图记录、入库记录和导出记录
- 向 Codex skill 暴露稳定命令或 HTTP API

前端负责：

- 展示项目、角色、服装、任务和运行结果
- 引导用户填写事件、姿态、动作、镜头和输出规格
- 展示本次运行使用了哪些角色资产
- 提供启动生成、选择候选、框选修复、入库和导出入口
- 调用后端 API 更新状态

## 本地生产包

每次工作流运行会生成一个本地生产包：

```text
tasks/<task_id>/production/<run_id>/
  production.json
  workflow_input.json
  asset_bundle/
    references/
    controls/
    masks/
  outputs/
  run_log.json
```

`production.json` 记录任务、角色、服装、资产选择结果、Prompt 文件版本、工作流 preset、模型资源和输出规格。

`workflow_input.json` 是交给 ComfyUI 适配层的输入。它保存节点注入参数、图片路径、控制图路径、模型资源和导出目录。

`asset_bundle/` 保存本次运行使用的参考图和控制图副本。原始角色资产保持不变。

`outputs/` 保存本次工作流输出图片。

`run_log.json` 保存耗时、状态、错误、ComfyUI prompt id 和输出文件。

## 工作流类型

候选图工作流用于探索方向。它读取面部身份、三视图、服装设定和项目画风，生成多张候选图。

受控候选工作流用于更明确的姿态和构图。它在候选图基础上加入姿态控制图、线稿、深度图或已有草图。

精修工作流用于处理选中的候选图。它读取候选图作为源图，结合面部身份、服装设定和细节锚点进行低幅度重绘。

局部修复工作流用于框选区域。它读取源图、遮罩、相关细节参考和修复说明，只处理用户框出的区域。

高清导出工作流用于交付。它读取通过验收的图，进行放大、锐化、格式转换和项目命名。

## API 契约

第一版后端至少提供这些能力：

```text
GET  /api/projects
GET  /api/projects/{projectId}/characters
POST /api/tasks
GET  /api/tasks/{taskId}
POST /api/tasks/{taskId}/production-runs
GET  /api/tasks/{taskId}/production-runs/{runId}
POST /api/tasks/{taskId}/imports
POST /api/tasks/{taskId}/review
POST /api/tasks/{taskId}/export
```

Codex skill 调用同一套 API 或等价 CLI。
