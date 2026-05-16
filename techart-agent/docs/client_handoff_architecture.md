# 客户端与 Handoff 架构

`techart-agent` 面向 galgame 开发者，第一版采用“生产包 + 手动 ChatGPT 网页生成 + 结果导回”的工作方式。系统负责准备生产材料、记录来源、导入结果和维护资产库；用户在 ChatGPT Plus 网页完成实际图像生成。

## 产品流程

```text
创建美术任务
  -> 选择项目、角色、服装、资产类型、事件和动作
  -> 生成 handoff 包
  -> 用户打开 ChatGPT 网页
  -> 用户上传参考图并复制任务文本
  -> 用户下载生成图片
  -> 用户把图片导回 techart-agent
  -> 审图、精修、入库、导出
```

## 前后端边界

后端负责：

- 读取项目资产、角色资产、服装资产和模型资源配置
- 创建任务和任务组
- 选择本次生产需要的参考图
- 生成 handoff 包
- 导入用户下载的图片
- 保存审图记录、入库记录和导出记录
- 向 Codex skill 暴露稳定命令或 HTTP API

前端负责：

- 展示项目、角色、服装和任务
- 引导用户填写事件、姿态、动作、镜头和输出规格
- 展示 handoff 包内容
- 提供复制文本、打开目录、导入图片、审图和导出按钮
- 调用后端 API 更新状态

前端不直接拼接 prompt，不直接扫描内部目录，不直接改写角色资产。它通过后端接口完成操作。

## Handoff 包

每个 handoff 包保存一次向 ChatGPT 网页交接的全部材料：

```text
tasks/<task_id>/handoff/<handoff_id>/
  handoff.json
  prompt_to_copy.md
  reference_index.md
  upload/
    01_face_reference.png
    02_turnaround_reference.png
    03_outfit_reference.png
  contact_sheet.png
  import_instructions.md
```

`handoff.json` 是机器记录。它保存任务、角色、服装、参考图、prompt 模板版本、生成目标和导入状态。

`prompt_to_copy.md` 是用户复制到 ChatGPT 网页的文本。正文模板由项目负责人维护，系统只填变量。

`reference_index.md` 说明每张上传图的用途。用户可以检查，也可以贴给 ChatGPT。

`upload/` 保存本次需要上传的参考图副本。

`contact_sheet.png` 把参考图拼成总览，方便用户确认本次包是否完整。

`import_instructions.md` 说明用户如何把 ChatGPT 下载结果导回任务。

## API 契约

第一版后端至少提供这些能力：

```text
GET  /api/projects
GET  /api/projects/{projectId}/characters
POST /api/tasks
GET  /api/tasks/{taskId}
POST /api/tasks/{taskId}/handoff
GET  /api/tasks/{taskId}/handoff/{handoffId}
POST /api/tasks/{taskId}/imports
POST /api/tasks/{taskId}/review
POST /api/tasks/{taskId}/export
```

Codex skill 可以调用同一套能力，也可以调用等价 CLI。Skill 的角色是外部操作者，不能绕过 API 直接篡改内部资产。

## 可插拔点

第一版目标是 ChatGPT Plus 网页手动生产。后续保留这些可插拔点：

- handoff target：ChatGPT 网页、GPT Image API、本地 ComfyUI
- reference selector：不同资产类型选择不同参考图
- importer：手动下载图片导入、目录监听导入、压缩包导入
- exporter：Ren'Py 规格、Unity 规格、普通图片目录
- reviewer：人工审图、AI 辅助审图、批量质量检查

插件只能通过清楚的输入输出契约接入。插件结果要写入任务记录，方便复盘和回滚。
