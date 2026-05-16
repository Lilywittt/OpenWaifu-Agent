# 目录结构

`techart-agent` 采用项目级资产目录。配置、文档和代码进入仓库；项目素材、生成图、模型文件和运行态默认本地管理。

## 顶层目录

```text
techart-agent/
  config/
  docs/
  prompts/
  projects/
  runtime/
  src/
  tools/
```

`config/` 保存产品配置、资产类型、导出规格、工作流预设、模型后端和审图标签。

`docs/` 保存产品架构、数据契约和实施说明。

`prompts/` 保存业务 Prompt 文件。Prompt 正文由项目负责人维护，代码只负责加载、校验、版本记录和占位符填充。

`projects/` 保存本地项目资产。项目里通常会有图片、模型和人工资料，默认本地管理。

`runtime/` 保存缓存、临时图、队列状态和生成过程文件。

`src/` 保存产品代码，按资产、任务、工作流、审图、导出和反馈分层。

`tools/` 保存检查、导入、导出和维护脚本。

## 项目目录

```text
projects/<project_id>/
  project.json
  characters/
  tasks/
  assets/
  exports/
  feedback/
```

`project.json` 保存项目名、画风、默认导出规格、默认工作流和当前版本。

`characters/` 保存角色资产库。

`tasks/` 保存美术任务和运行记录。

`assets/` 保存通过验收后入库的素材。

`exports/` 保存交付给游戏工程的图片。

`feedback/` 保存审图结果、弃用原因、人工修复记录和训练数据候选清单。

## 任务目录

```text
tasks/<task_id>/
  task.json
  inputs/
  runs/
  candidates/
  refinements/
  inpaint/
  exports/
  review.json
```

`task.json` 保存任务目标、资产类型、角色、画面需求、工作流预设和导出规格。

`inputs/` 保存参考图、草图、遮罩和人工上传材料。

`runs/` 保存工作流运行记录。

`candidates/` 保存候选图。

`refinements/` 保存精修图。

`inpaint/` 保存局部修复结果。

`exports/` 保存该任务导出的最终文件。

`review.json` 保存收藏、弃用、入库和问题标注。
