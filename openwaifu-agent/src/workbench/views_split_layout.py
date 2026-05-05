from __future__ import annotations


_SPLIT_LAYOUT_STYLE = """
  .workbench-split-root,
  .workbench-split-root body {
    height: 100%;
  }
  body.workbench-split-root {
    overflow: hidden;
  }
  .page.workbench-page {
    width: min(1600px, calc(100vw - 24px));
    margin: 12px auto;
    height: calc(100vh - 24px);
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    gap: 16px;
  }
  .workbench-workspace {
    min-height: 0;
    display: grid;
    grid-template-columns: minmax(440px, 540px) minmax(0, 1fr);
    gap: 16px;
  }
  .workbench-pane {
    min-height: 0;
    overflow: auto;
    overscroll-behavior: contain;
    padding-right: 4px;
  }
  .workbench-pane-stack {
    display: grid;
    gap: 16px;
    padding: 0 2px 20px 0;
  }
  .workbench-pane-stack > .card {
    margin: 0;
  }
  .workbench-pane-right .workbench-pane-stack {
    min-height: 100%;
  }
  .workbench-pane-right .card {
    min-height: 100%;
  }
  .workbench-pane::-webkit-scrollbar {
    width: 10px;
  }
  .workbench-pane::-webkit-scrollbar-thumb {
    border-radius: 999px;
    background: rgba(107, 119, 131, 0.28);
  }
  .workbench-pane::-webkit-scrollbar-track {
    background: transparent;
  }
  @media (max-width: 1200px) {
    body.workbench-split-root {
      overflow: auto;
    }
    .page.workbench-page {
      height: auto;
      min-height: 0;
    }
    .workbench-workspace {
      grid-template-columns: 1fr;
    }
    .workbench-pane {
      overflow: visible;
      min-height: auto;
      padding-right: 0;
    }
  }
"""


_SPLIT_LAYOUT_SCRIPT = """
<script>
  (() => {
    const page = document.querySelector(".page");
    const grid = page?.querySelector(":scope > .grid");
    const detailCard = document.getElementById("detail-root")?.closest("section.card");
    if (!page || !grid || !detailCard || page.querySelector(":scope > .workbench-workspace")) {
      return;
    }

    const sections = Array.from(grid.children).filter((element) => element.matches("section.card"));
    const leftSections = sections.filter((section) => section !== detailCard);
    if (!leftSections.length) {
      return;
    }

    document.documentElement.classList.add("workbench-split-root");
    document.body.classList.add("workbench-split-root");
    document.body.setAttribute("data-workbench-split", "1");
    page.classList.add("workbench-page");

    const workspace = document.createElement("div");
    workspace.className = "workbench-workspace";
    workspace.setAttribute("data-workbench-workspace", "1");

    const leftPane = document.createElement("div");
    leftPane.className = "workbench-pane workbench-pane-left";
    leftPane.setAttribute("data-workbench-pane", "left");

    const rightPane = document.createElement("div");
    rightPane.className = "workbench-pane workbench-pane-right";
    rightPane.setAttribute("data-workbench-pane", "right");

    const leftStack = document.createElement("div");
    leftStack.className = "workbench-pane-stack";

    const rightStack = document.createElement("div");
    rightStack.className = "workbench-pane-stack";

    for (const section of leftSections) {
      leftStack.appendChild(section);
    }
    rightStack.appendChild(detailCard);

    leftPane.appendChild(leftStack);
    rightPane.appendChild(rightStack);
    workspace.appendChild(leftPane);
    workspace.appendChild(rightPane);
    grid.replaceWith(workspace);
    window.__OPENWAIFU_WORKBENCH_SPLIT_READY__ = true;
  })();
</script>
"""


def _inject_before(source: str, marker: str, content: str) -> str:
    if marker not in source:
        raise RuntimeError(f"Workbench template marker not found: {marker}")
    return source.replace(marker, content + marker, 1)


def apply_workbench_split_layout(html: str, *, body_attributes: tuple[str, ...] = ()) -> str:
    body_attr_text = " ".join(part.strip() for part in body_attributes if part and part.strip())
    body_open = "<body>" if not body_attr_text else f"<body {body_attr_text}>"
    updated = html.replace("<body>", body_open, 1)
    updated = _inject_before(updated, "</style>", _SPLIT_LAYOUT_STYLE)
    updated = _inject_before(updated, "</body>", _SPLIT_LAYOUT_SCRIPT)
    return updated
