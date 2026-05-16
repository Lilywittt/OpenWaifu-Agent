# Prompt 治理

Prompt 是 `techart-agent` 的核心生产资产。控制工作流的业务 Prompt 正文由项目负责人亲自维护。代码和工具可以管理文件、版本、占位符和运行记录。

## 权责

项目负责人维护：

- 候选图生成 Prompt 正文
- 精修 Prompt 正文
- 局部修复 Prompt 正文
- 高清导出相关描述
- 质量评审 Prompt 正文
- 角色资产、服装资产和项目美术标准的表达方式

代码负责：

- 读取 Prompt 文件
- 校验占位符是否完整
- 填充任务输入、角色资产、服装资产和项目美术标准
- 记录 Prompt 文件路径、版本和 hash
- 将渲染后的 Prompt 写入运行记录
- 在缺失 Prompt 或占位符错误时阻止运行

## 目录

```text
prompts/
  README.md
  candidate/
    .gitkeep
  refine/
    .gitkeep
  inpaint/
    .gitkeep
  review/
    .gitkeep
```

这些目录先作为产品契约保留。后续写入具体 Prompt 正文前，需要项目负责人确认。

## 运行记录

每次工作流运行都要记录：

- prompt 文件路径
- prompt 版本
- prompt hash
- 渲染前变量
- 渲染后文本
- 调用的工作流 preset
- 输出图片路径

这样后续复跑、定位质量问题和整理训练数据时，可以知道图片来自哪一版 Prompt。
