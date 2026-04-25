import os
import shutil
import tempfile
import zipfile
from xml.etree import ElementTree as ET


ROOT_DIR = r"F:\openwaifu-workspace"
DOCX_NAME = next(name for name in os.listdir(ROOT_DIR) if name.lower().endswith(".docx"))
DOCX_PATH = os.path.join(ROOT_DIR, DOCX_NAME)
DOC_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": DOC_NS}

ET.register_namespace("w", DOC_NS)

REPLACEMENTS = {
    22: "OpenWaifu-Agent 是一个面向插画设计流程的 AI Agent 系统。我围绕“让想法稳定落到可用图片”这个目标，打通了创意规划、角色与场景设计、文案生成、Prompt 编译与审查、本地 ComfyUI 生图、结果管理和公网体验入口，做成了一条可运行、可复盘的内容生产链。",
    23: "本人独立负责项目从 0 到 1 的产品定义、系统设计、全栈实现、调试迭代和部署上线。围绕长链路 AI 任务容易失控的问题，我把流程拆成 creative、prompt_builder、prompt_guard、execution、publish 等阶段，并为各阶段定义清晰输入输出、状态流转和产物留档方式。",
    24: "在创意层，我重点解决“角色一致性”和“内容多样性”之间的矛盾：一方面沉淀稳定角色资产，另一方面引入外部灵感采样和场景设计输入，持续扩展动作、情绪、构图和环境变化，提升内容新鲜度，同时保持人物锚点稳定。",
    25: "在 Prompt 工程层，我实现了从结构化设计稿到 positive / negative prompt 的编译链，并加入冲突检测与最小修正机制，处理动作冲突、景别冲突、服装状态冲突和身体部位可见性冲突，提升生图前的可控性和最终结果稳定性。",
    26: "在 LLM 工程层，我封装了 DeepSeek API 调用、结构化输出解析、失败重试、JSON 修复和 trace 记录，使创意包、文案包、Prompt 包和审查报告能够稳定生成、可追踪、可调试，体现了我把大模型能力工程化落地的能力。",
    27: "在执行与交付层，我接入本地 ComfyUI 工作流，完成 workflow 模板加载、模型与 checkpoint 校验、健康检查、任务提交、轮询、结果回收和 run 级别快照管理；同时搭建了公共体验工作台、私有测试工作台和运维面板，并通过公网域名完成对外访问，体现了我从后端链路到前端体验、从本地执行到部署上线的完整交付能力。",
    28: "项目开发过程中，我深度使用 Codex、ChatGPT 等 AI 工具提升研发效率，但始终主动约束模块边界、接口职责、状态模型和目录结构，避免代码在快速迭代中失控。这体现了我不仅会“用 AI 写代码”，也能判断什么该交给 AI、什么必须由工程设计来兜底。",
}


def load_document_root():
    with zipfile.ZipFile(DOCX_PATH, "r") as source_zip:
        xml_bytes = source_zip.read("word/document.xml")
    return ET.fromstring(xml_bytes)


def collect_non_empty_paragraphs(root):
    paragraphs = []
    for paragraph in root.findall(".//w:p", NS):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", NS)]
        if "".join(texts).strip():
            paragraphs.append(paragraph)
    return paragraphs


def replace_paragraph_text(paragraph, text):
    text_nodes = paragraph.findall(".//w:t", NS)
    if not text_nodes:
        return
    text_nodes[0].text = text
    for node in text_nodes[1:]:
        node.text = ""


def save_document_root(root):
    fd, temp_path = tempfile.mkstemp(suffix=".docx", dir=ROOT_DIR)
    os.close(fd)
    try:
        with zipfile.ZipFile(DOCX_PATH, "r") as source_zip, zipfile.ZipFile(
            temp_path,
            "w",
            zipfile.ZIP_DEFLATED,
        ) as output_zip:
            for item in source_zip.infolist():
                payload = source_zip.read(item.filename)
                if item.filename == "word/document.xml":
                    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                output_zip.writestr(item, payload)
        shutil.move(temp_path, DOCX_PATH)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def main():
    root = load_document_root()
    paragraphs = collect_non_empty_paragraphs(root)
    for index, text in REPLACEMENTS.items():
        replace_paragraph_text(paragraphs[index - 1], text)
    save_document_root(root)
    print(DOCX_PATH)


if __name__ == "__main__":
    main()
