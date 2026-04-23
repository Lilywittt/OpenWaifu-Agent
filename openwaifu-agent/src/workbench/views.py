from __future__ import annotations


def render_content_workbench_html(*, project_name: str, refresh_seconds: int) -> str:
    refresh_ms = max(int(refresh_seconds), 2) * 1000
    refresh_label = max(int(refresh_seconds), 2)
    title_text = str(project_name).strip() or "内容工作台"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_text}</title>
  <style>
    :root {{
      --bg: #f5f1ea;
      --panel: #fffdf9;
      --ink: #21303a;
      --muted: #6b7783;
      --line: #ddd5c9;
      --accent: #8f5a2a;
      --accent-soft: #f1e2d3;
      --accent-strong: #694320;
      --ok: #2f6f63;
      --warn: #c7782e;
      --danger: #b54c3c;
      --shadow: 0 16px 34px rgba(33, 48, 58, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(143, 90, 42, 0.1), transparent 28%),
        linear-gradient(180deg, #f8f4ee 0%, var(--bg) 100%);
      min-height: 100vh;
    }}
    .page {{
      width: min(1480px, calc(100vw - 32px));
      margin: 24px auto 40px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(143, 90, 42, 0.97), rgba(52, 68, 84, 0.96));
      color: #fffaf6;
      padding: 24px 28px;
      border-radius: 24px;
      box-shadow: var(--shadow);
      display: grid;
      gap: 14px;
    }}
    .hero-top {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      flex-wrap: wrap;
    }}
    h1 {{
      margin: 0;
      font-size: 30px;
      line-height: 1.12;
    }}
    .hero-sub {{
      color: rgba(255, 250, 246, 0.84);
      font-size: 14px;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 10px 14px;
      background: rgba(255, 255, 255, 0.14);
      font-size: 13px;
      font-weight: 700;
    }}
    .toolbar {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
    }}
    button, select, input, textarea {{
      font: inherit;
    }}
    button {{
      appearance: none;
      border: 0;
      border-radius: 999px;
      padding: 11px 16px;
      font-weight: 700;
      cursor: pointer;
      transition: transform 120ms ease, box-shadow 120ms ease, opacity 120ms ease;
    }}
    button:hover {{
      transform: translateY(-1px);
      box-shadow: 0 10px 18px rgba(33, 48, 58, 0.1);
    }}
    button:disabled {{
      cursor: not-allowed;
      opacity: 0.55;
      transform: none;
      box-shadow: none;
    }}
    .btn-primary {{
      background: #fffaf6;
      color: var(--accent-strong);
    }}
    .meta {{
      display: flex;
      gap: 18px;
      flex-wrap: wrap;
      color: rgba(255, 250, 246, 0.88);
      font-size: 13px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 16px;
      margin-top: 18px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 18px;
      box-shadow: var(--shadow);
    }}
    .span-4 {{ grid-column: span 4; }}
    .span-5 {{ grid-column: span 5; }}
    .span-7 {{ grid-column: span 7; }}
    .span-8 {{ grid-column: span 8; }}
    .card h2 {{
      margin: 0 0 12px;
      font-size: 16px;
    }}
    .card-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 12px;
      flex-wrap: wrap;
    }}
    .form-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}
    .field {{
      display: grid;
      gap: 8px;
    }}
    .field.full {{
      grid-column: 1 / -1;
    }}
    label {{
      font-size: 13px;
      font-weight: 700;
      color: var(--muted);
    }}
    input, select, textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px 14px;
      background: #fffdfa;
      color: var(--ink);
    }}
    textarea {{
      min-height: 220px;
      resize: vertical;
      line-height: 1.6;
    }}
    .hint {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
    }}
    .actions {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 4px;
    }}
    .panel-actions button {{
      background: var(--accent-soft);
      color: var(--accent-strong);
    }}
    .status-stack {{
      display: grid;
      gap: 10px;
    }}
    .status-hero {{
      display: grid;
      gap: 6px;
      padding: 14px;
      border-radius: 16px;
      background: linear-gradient(180deg, #fff7ef 0%, #f7efe4 100%);
      border: 1px solid rgba(143, 90, 42, 0.18);
    }}
    .status-value {{
      font-size: 26px;
      line-height: 1;
      font-weight: 800;
    }}
    .muted {{ color: var(--muted); }}
    .status-ok {{ color: var(--ok); }}
    .status-warn {{ color: var(--warn); }}
    .status-danger {{ color: var(--danger); }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 12px;
      font-weight: 700;
      background: var(--accent-soft);
      color: var(--accent-strong);
    }}
    .history-panel {{
      display: grid;
      gap: 12px;
    }}
    .history-group {{
      display: grid;
      gap: 8px;
    }}
    .history-group[hidden] {{
      display: none;
    }}
    .history-group-title {{
      font-size: 12px;
      font-weight: 700;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .history-toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .history-filters {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .filter-chip {{
      border: 1px solid var(--line);
      background: #f8f3eb;
      color: var(--accent-strong);
      padding: 8px 12px;
      font-size: 12px;
    }}
    .filter-chip.active {{
      background: var(--accent);
      color: #fffaf6;
      border-color: rgba(143, 90, 42, 0.48);
    }}
    .history-list {{
      display: grid;
      gap: 10px;
      margin: 0;
      padding: 0;
      list-style: none;
    }}
    .history-item {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 12px;
      background: rgba(255, 255, 255, 0.8);
      display: grid;
      gap: 10px;
      cursor: pointer;
    }}
    .history-item.active {{
      border-color: rgba(143, 90, 42, 0.52);
      box-shadow: inset 0 0 0 1px rgba(143, 90, 42, 0.18);
      background: #fff8f1;
    }}
    .history-item.deleted {{
      opacity: 0.7;
    }}
    .history-main {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 84px;
      gap: 12px;
      align-items: start;
    }}
    .history-thumb {{
      width: 84px;
      aspect-ratio: 1 / 1;
      object-fit: cover;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, #f7f3eb 0%, #efe6da 100%);
    }}
    .history-thumb.empty {{
      display: grid;
      place-items: center;
      color: var(--muted);
      font-size: 12px;
    }}
    .history-top {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      flex-wrap: wrap;
    }}
    .history-title {{
      font-weight: 700;
      line-height: 1.5;
    }}
    .history-meta {{
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
    }}
    .history-foot {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .history-open {{
      background: #f7f2ea;
      color: var(--accent-strong);
      padding: 8px 12px;
      font-size: 12px;
    }}
    .detail-actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .review-toolbar {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
      margin-top: 12px;
      margin-bottom: 6px;
    }}
    .review-toolbar input {{
      flex: 1 1 320px;
      min-width: 240px;
    }}
    .detail-actions button {{
      background: #f7f2ea;
      color: var(--accent-strong);
      padding: 8px 12px;
      font-size: 12px;
    }}
    .detail-actions .danger {{
      background: #fff0ed;
      color: var(--danger);
    }}
    .section-nav {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 18px;
      padding-top: 16px;
      border-top: 1px solid var(--line);
    }}
    .section-nav a {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 8px 12px;
      text-decoration: none;
      background: #f7f2ea;
      color: var(--accent-strong);
      font-size: 12px;
      font-weight: 700;
    }}
    .section-grid {{
      display: grid;
      gap: 14px;
    }}
    .section-card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
      background: rgba(255, 255, 255, 0.72);
    }}
    .section-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 12px;
    }}
    .section-text {{
      margin-top: 12px;
      white-space: pre-wrap;
      line-height: 1.7;
    }}
    .diff-blocks {{
      display: grid;
      gap: 12px;
      margin-top: 12px;
    }}
    .diff-block {{
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      background: rgba(255, 255, 255, 0.82);
    }}
    .diff-title {{
      font-size: 12px;
      font-weight: 700;
      color: var(--muted);
      margin-bottom: 8px;
    }}
    .diff-content {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px 6px;
      line-height: 1.7;
    }}
    .diff-token {{
      display: inline-flex;
      align-items: center;
      padding: 3px 8px;
      border-radius: 999px;
      background: #f3eee6;
      border: 1px solid rgba(33, 48, 58, 0.06);
    }}
    .diff-token.changed.before {{
      background: #fff1ee;
      border-color: rgba(181, 76, 60, 0.18);
      color: var(--danger);
    }}
    .diff-token.changed.after {{
      background: #eaf6f2;
      border-color: rgba(47, 111, 99, 0.18);
      color: var(--ok);
    }}
    .raw-toggle {{
      margin-top: 14px;
      border-top: 1px dashed var(--line);
      padding-top: 12px;
    }}
    details > summary {{
      cursor: pointer;
      color: var(--accent-strong);
      font-weight: 700;
      user-select: none;
    }}
    pre {{
      margin: 10px 0 0;
      border-radius: 14px;
      padding: 14px;
      background: #1d2430;
      color: #f3f6f9;
      font-family: ui-monospace, "Cascadia Mono", Consolas, monospace;
      font-size: 12px;
      line-height: 1.6;
      overflow-x: auto;
      overflow-y: visible;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .detail-hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
      gap: 16px;
      align-items: start;
    }}
    .preview-link {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      color: inherit;
      text-decoration: none;
    }}
    .preview-image {{
      width: 100%;
      aspect-ratio: 1 / 1;
      object-fit: cover;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, #f7f3eb 0%, #efe6da 100%);
    }}
    .preview-path {{
      display: block;
      margin-top: 8px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.5;
      word-break: break-all;
    }}
    .detail-summary {{
      display: grid;
      gap: 10px;
    }}
    .summary-meta {{
      display: grid;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
    }}
    .empty {{
      color: var(--muted);
      padding: 12px 0;
    }}
    .message {{
      min-height: 24px;
      font-size: 13px;
      color: var(--muted);
    }}
    .message.error {{ color: var(--danger); }}
    .message.success {{ color: var(--ok); }}
    .mono {{
      font-family: ui-monospace, "Cascadia Mono", Consolas, monospace;
      font-size: 12px;
      word-break: break-all;
    }}
    @media (max-width: 1180px) {{
      .span-4, .span-5, .span-7, .span-8 {{ grid-column: span 12; }}
      .detail-hero {{ grid-template-columns: 1fr; }}
      .form-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <div class="hero-top">
        <div>
          <h1 id="hero-title">{title_text}</h1>
        </div>
        <div class="toolbar">
          <div class="pill" id="hero-status">正在读取状态</div>
          <button type="button" id="refresh-btn" class="btn-primary">立即刷新</button>
        </div>
      </div>
      <div class="meta">
        <span id="meta-generated">最后刷新：-</span>
        <span id="meta-project">项目目录：-</span>
        <span>自动刷新：每 {refresh_label} 秒</span>
      </div>
    </section>

    <div class="grid">
      <section class="card span-7">
        <div class="card-head">
          <h2>发起任务</h2>
          <div class="panel-actions">
            <button type="button" id="fill-last-btn">载入上一次请求</button>
            <button type="button" id="clear-form-btn">清空输入</button>
          </div>
        </div>
        <div class="form-grid">
          <div class="field">
            <label for="source-kind">任务起点</label>
            <select id="source-kind"></select>
          </div>
          <div class="field">
            <label for="end-stage">任务终点</label>
            <select id="end-stage"></select>
          </div>
          <div class="field full">
            <label for="request-label">运行标签</label>
            <input id="request-label" type="text" placeholder="可选，用于区分本次任务">
          </div>
          <div class="field full" id="scene-draft-field">
            <label for="scene-draft-text">场景稿正文 / JSON</label>
            <textarea id="scene-draft-text" placeholder="直接输入场景稿正文，或填 scenePremiseZh/worldSceneZh JSON"></textarea>
          </div>
          <div class="field full" id="source-path-field">
            <label for="source-path">已有文件或目录路径</label>
            <input id="source-path" type="text" placeholder="支持文件路径，也支持包含目标文件的 run/creative 目录">
          </div>
          <div class="field full" id="source-content-field" style="display: none;">
            <label for="source-content">正文内容</label>
            <textarea id="source-content" placeholder="直接写内容，工作台会自动补成对应输入包。"></textarea>
          </div>
          <div class="field full" id="creative-scene-premise-field" style="display: none;">
            <label for="creative-scene-premise">场景标题</label>
            <input id="creative-scene-premise" type="text" placeholder="可选，只写标题即可">
          </div>
          <div class="field full" id="creative-world-scene-field" style="display: none;">
            <label for="creative-world-scene">场景正文</label>
            <textarea id="creative-world-scene" placeholder="必填，直接写场景正文。"></textarea>
          </div>
          <div class="field full" id="creative-environment-field" style="display: none;">
            <label for="creative-environment">环境设计稿</label>
            <textarea id="creative-environment" placeholder="可选，直接写环境、布景与光影设计内容。"></textarea>
          </div>
          <div class="field full" id="creative-styling-field" style="display: none;">
            <label for="creative-styling">造型设计稿</label>
            <textarea id="creative-styling" placeholder="可选，直接写服装与造型设计内容。"></textarea>
          </div>
          <div class="field full" id="creative-action-field" style="display: none;">
            <label for="creative-action">动作设计稿</label>
            <textarea id="creative-action" placeholder="可选，直接写动作、姿态与神态设计内容。"></textarea>
          </div>
          <div class="field full" id="prompt-positive-field" style="display: none;">
            <label for="prompt-positive">正向 Prompt</label>
            <textarea id="prompt-positive" placeholder="必填，直接写正向 Prompt。"></textarea>
          </div>
          <div class="field full" id="prompt-negative-field" style="display: none;">
            <label for="prompt-negative">负向 Prompt</label>
            <textarea id="prompt-negative" placeholder="必填，直接写负向 Prompt。"></textarea>
          </div>
          <div class="field full">
            <div class="hint" id="source-hint">-</div>
          </div>
        </div>
        <div class="actions">
          <button type="button" id="start-btn" class="btn-primary">开始运行</button>
          <button type="button" id="stop-btn">停止当前任务</button>
          <button type="button" id="rerun-btn">复跑上一轮</button>
        </div>
        <div class="message" id="action-message"></div>
      </section>

      <section class="card span-5">
        <h2>当前状态</h2>
        <div class="status-stack">
          <div class="status-hero">
            <div class="status-value" id="status-value">-</div>
            <div id="status-stage" class="muted">-</div>
            <div id="status-stage-detail" class="muted">-</div>
          </div>
          <div id="status-run-id" class="mono muted">runId：-</div>
          <div id="status-run-root" class="mono muted">运行目录：-</div>
          <div id="status-slot" class="muted">执行位：-</div>
          <div id="status-error" class="muted" style="display: none;"></div>
        </div>
      </section>

      <section class="card span-4">
        <div class="history-panel">
          <div class="card-head" style="margin-bottom: 0;">
            <h2>最近任务</h2>
            <div class="muted" id="history-summary">-</div>
          </div>
          <div class="history-toolbar">
            <div class="history-filters">
              <button type="button" class="filter-chip" id="history-filter-favorites">收藏</button>
              <button type="button" class="filter-chip active" id="history-filter-active">有效</button>
              <button type="button" class="filter-chip" id="history-filter-all">全部</button>
              <button type="button" class="filter-chip" id="history-filter-deleted">已删除</button>
            </div>
            <button type="button" class="filter-chip" id="history-load-more" hidden>加载更多</button>
          </div>
          <div class="history-group" id="current-run-group" hidden>
            <div class="history-group-title">当前运行</div>
            <ul class="history-list" id="current-run-list"></ul>
          </div>
          <div class="history-group">
            <div class="history-group-title">最近任务</div>
          <ul class="history-list" id="history-list">
            <li class="empty">还没有任务记录。</li>
          </ul>
          </div>
        </div>
      </section>

      <section class="card span-8">
        <div class="card-head">
          <h2>当前 / 已选任务详情</h2>
          <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
            <div class="detail-actions" id="detail-actions"></div>
            <div class="badge" id="detail-badge">未选择任务</div>
          </div>
        </div>
        <div id="detail-root" class="empty">开始一轮任务后，这里会实时展开它的中间产物和最终产物。</div>
      </section>
    </div>
  </div>

  <script>
    const refreshMs = {refresh_ms};
    const hiddenRefreshMs = Math.max(refreshMs * 4, 30000);
    let currentSnapshot = null;
    let selectedRunId = "";
    let historyFilter = "active";
    let historyLimit = 0;
    let reviewedPath = "";
    let reviewedPathDetail = null;
    let snapshotPollTimer = null;
    let snapshotFetchPromise = null;
    let initializedForm = false;
    let expandedRawKeys = new Set();
    let detailSuspendUntil = 0;
    let lastHistoryListRenderKey = "";
    let lastDetailRenderKey = "";

    function nextPollDelayMs() {{
      return document.hidden ? hiddenRefreshMs : refreshMs;
    }}

    function scheduleSnapshotPoll(delayMs = nextPollDelayMs()) {{
      if (snapshotPollTimer) {{
        window.clearTimeout(snapshotPollTimer);
      }}
      snapshotPollTimer = window.setTimeout(() => {{
        fetchSnapshot().catch(() => null);
      }}, delayMs);
    }}

    function modePreferenceStorageKey(snapshot = currentSnapshot) {{
      return currentPermissions(snapshot).public
        ? "public-workbench-mode-preference-v1"
        : "content-workbench-mode-preference-v1";
    }}

    function normalizeText(value) {{
      return String(value || "").trim();
    }}

    function clearReviewedPathDetail() {{
      reviewedPath = "";
      reviewedPathDetail = null;
      const input = document.getElementById("review-path-input");
      if (input) {{
        input.value = "";
      }}
    }}

    function rememberExpandedDetails() {{
      expandedRawKeys = new Set(
        Array.from(document.querySelectorAll("details[data-raw-key][open]"))
          .map((element) => element.getAttribute("data-raw-key"))
          .filter(Boolean)
      );
    }}

    function statusClass(status) {{
      const normalized = normalizeText(status);
      if (["completed", "idle"].includes(normalized)) return "status-ok";
      if (["stopping", "interrupted"].includes(normalized)) return "status-warn";
      if (["failed"].includes(normalized)) return "status-danger";
      return "";
    }}

    function configuredHistoryLimit(snapshot) {{
      const raw = Number(snapshot?.config?.historyLimit || 0);
      return raw > 0 ? raw : 30;
    }}

    function currentPermissions(snapshot = currentSnapshot) {{
      return snapshot?.config?.permissions || {{}};
    }}

    function decorateSourceKindLabel(sourceKindId, baseLabel, snapshot = currentSnapshot) {{
      const label = normalizeText(baseLabel);
      if (!currentPermissions(snapshot).public) return label;
      if (label.includes("（体验者推荐点这里）")) return label;
      const sourceKind = normalizeText(sourceKindId);
      if (sourceKind === "live_sampling" || sourceKind === "scene_draft_text") {{
        return `${{label}}（体验者推荐点这里）`;
      }}
      return label;
    }}

    function hasHistoryFilter(snapshot, filterId) {{
      const filters = Array.isArray(snapshot?.config?.historyFilters) ? snapshot.config.historyFilters : [];
      return filters.some((item) => normalizeText(item?.id) === normalizeText(filterId));
    }}

    function ensureHistoryLimit(snapshot) {{
      if (Number(historyLimit) > 0) return;
      historyLimit = configuredHistoryLimit(snapshot);
    }}

    function stableJson(value) {{
      try {{
        return JSON.stringify(value ?? null);
      }} catch (_error) {{
        return String(value ?? "");
      }}
    }}

    function applyActionMessage(text, kind = "") {{
      const element = document.getElementById("action-message");
      element.textContent = text || "";
      element.className = "message" + (kind ? " " + kind : "");
    }}

    function buildSourceKindMap(sourceKinds) {{
      const map = new Map();
      (sourceKinds || []).forEach((item) => map.set(item.id, item));
      return map;
    }}

    function requestHasUsableMode(snapshot, request) {{
      if (!request || typeof request !== "object") return false;
      const sourceKind = normalizeText(request.sourceKind);
      if (!sourceKind) return false;
      const sourceKinds = buildSourceKindMap(snapshot?.config?.sourceKinds || []);
      const sourceConfig = sourceKinds.get(sourceKind);
      if (!sourceConfig) return false;
      const endStage = normalizeText(request.endStage);
      if (!endStage) return true;
      const allowedStages = Array.isArray(sourceConfig.allowedEndStages) ? sourceConfig.allowedEndStages : [];
      return allowedStages.some((item) => normalizeText(item.id) === endStage);
    }}

    function readModePreference(snapshot = currentSnapshot) {{
      try {{
        const raw = window.localStorage.getItem(modePreferenceStorageKey(snapshot));
        if (!raw) return null;
        const payload = JSON.parse(raw);
        return payload && typeof payload === "object" ? payload : null;
      }} catch (_error) {{
        return null;
      }}
    }}

    function writeModePreference(request, snapshot = currentSnapshot) {{
      try {{
        window.localStorage.setItem(
          modePreferenceStorageKey(snapshot),
          JSON.stringify({{
            sourceKind: normalizeText(request?.sourceKind),
            endStage: normalizeText(request?.endStage),
          }})
        );
      }} catch (_error) {{
        return;
      }}
    }}

    function persistCurrentModePreference(snapshot = currentSnapshot) {{
      writeModePreference({{
        sourceKind: document.getElementById("source-kind").value,
        endStage: document.getElementById("end-stage").value,
      }}, snapshot);
    }}

    function applyRequestModeToForm(request, snapshot) {{
      if (!requestHasUsableMode(snapshot, request)) return false;
      const sourceKind = normalizeText(request.sourceKind);
      const endStage = normalizeText(request.endStage);
      const sourceSelect = document.getElementById("source-kind");
      sourceSelect.value = sourceKind;
      updateEndStageOptions(snapshot);
      if (endStage) {{
        document.getElementById("end-stage").value = endStage;
      }}
      updateSourceFields(snapshot);
      persistCurrentModePreference(snapshot);
      return true;
    }}

    function ensureFormOptions(snapshot) {{
      const config = snapshot?.config || {{}};
      const sourceKinds = Array.isArray(config.sourceKinds) ? config.sourceKinds : [];
      const sourceSelect = document.getElementById("source-kind");
      const previousValue = normalizeText(sourceSelect.value);
      sourceSelect.innerHTML = sourceKinds
        .map((item) => `<option value="${{item.id}}">${{decorateSourceKindLabel(item.id, item.label, snapshot)}}</option>`)
        .join("");
      if (sourceKinds.some((item) => item.id === previousValue)) {{
        sourceSelect.value = previousValue;
      }} else {{
        sourceSelect.value = "";
      }}
      sourceSelect.dataset.ready = "1";
      updateEndStageOptions(snapshot);
    }}

    function updateEndStageOptions(snapshot, options = {{}}) {{
      const sourceSelect = document.getElementById("source-kind");
      const endSelect = document.getElementById("end-stage");
      const sourceKinds = buildSourceKindMap(snapshot?.config?.sourceKinds || []);
      const sourceKind = normalizeText(sourceSelect.value);
      const sourceConfig = sourceKinds.get(sourceKind);
      const allowedStages = Array.isArray(sourceConfig?.allowedEndStages) ? sourceConfig.allowedEndStages : [];
      const previousValue = normalizeText(endSelect.value);
      endSelect.innerHTML = allowedStages
        .map((item) => `<option value="${{item.id}}">${{item.label}}</option>`)
        .join("");
      let nextValue = "";
      if (allowedStages.some((item) => item.id === previousValue)) {{
        nextValue = previousValue;
      }} else if (allowedStages.length) {{
        nextValue = options.preferFirstStage ? allowedStages[0].id : allowedStages[allowedStages.length - 1].id;
      }}
      endSelect.value = nextValue;
      updateSourceFields(snapshot);
    }}

    function updateSourceFields(snapshot) {{
      const sourceSelect = document.getElementById("source-kind");
      const sourceKinds = buildSourceKindMap(snapshot?.config?.sourceKinds || []);
      const sourceKind = normalizeText(sourceSelect.value);
      const sourceConfig = sourceKinds.get(sourceKind);
      const showSceneDraftText = sourceKind === "scene_draft_text";
      const showSourcePath = ["scene_draft_file", "sample_file", "creative_package_file", "prompt_package_file"].includes(sourceKind);
      const showSourceContent = sourceKind === "sample_text";
      const showCreativeEditor = sourceKind === "creative_package_text";
      const showPromptEditor = sourceKind === "prompt_package_text";
      document.getElementById("scene-draft-field").style.display = showSceneDraftText ? "" : "none";
      document.getElementById("source-path-field").style.display = showSourcePath ? "" : "none";
      document.getElementById("source-content-field").style.display = showSourceContent ? "" : "none";
      document.getElementById("creative-scene-premise-field").style.display = showCreativeEditor ? "" : "none";
      document.getElementById("creative-world-scene-field").style.display = showCreativeEditor ? "" : "none";
      document.getElementById("creative-environment-field").style.display = showCreativeEditor ? "" : "none";
      document.getElementById("creative-styling-field").style.display = showCreativeEditor ? "" : "none";
      document.getElementById("creative-action-field").style.display = showCreativeEditor ? "" : "none";
      document.getElementById("prompt-positive-field").style.display = showPromptEditor ? "" : "none";
      document.getElementById("prompt-negative-field").style.display = showPromptEditor ? "" : "none";
      document.getElementById("source-hint").textContent = sourceConfig?.hint || "";
    }}

    function applyRequestToForm(request) {{
      if (!request || typeof request !== "object") return;
      const sourceKind = normalizeText(request.sourceKind);
      const sourceSelect = document.getElementById("source-kind");
      if (sourceKind) sourceSelect.value = sourceKind;
      updateEndStageOptions(currentSnapshot || {{ config: {{ sourceKinds: [] }} }});
      const endStage = normalizeText(request.endStage);
      if (endStage) document.getElementById("end-stage").value = endStage;
      document.getElementById("request-label").value = normalizeText(request.label);
      document.getElementById("scene-draft-text").value = request.sceneDraftText || "";
      document.getElementById("source-path").value = request.sourcePath || "";
      document.getElementById("source-content").value = request.sourceContent || "";
      document.getElementById("creative-scene-premise").value = request.scenePremiseText || "";
      document.getElementById("creative-world-scene").value = request.worldSceneText || "";
      document.getElementById("creative-environment").value = request.environmentDesignText || "";
      document.getElementById("creative-styling").value = request.stylingDesignText || "";
      document.getElementById("creative-action").value = request.actionDesignText || "";
      document.getElementById("prompt-positive").value = request.positivePromptText || "";
      document.getElementById("prompt-negative").value = request.negativePromptText || "";
      updateSourceFields(currentSnapshot || {{ config: {{ sourceKinds: [] }} }});
      persistCurrentModePreference();
    }}

    function initializeDefaultForm(snapshot) {{
      const sourceKinds = Array.isArray(snapshot?.config?.sourceKinds) ? snapshot.config.sourceKinds : [];
      const sourceSelect = document.getElementById("source-kind");
      if (normalizeText(sourceSelect.value)) {{
        updateEndStageOptions(snapshot);
        persistCurrentModePreference();
        return;
      }}
      if (applyRequestModeToForm(readModePreference(snapshot) || {{}}, snapshot)) {{
        return;
      }}
      if (applyRequestModeToForm(snapshot?.lastRequest || {{}}, snapshot)) {{
        return;
      }}
      if (sourceKinds.length) {{
        sourceSelect.value = sourceKinds[0].id;
      }}
      updateEndStageOptions(snapshot);
      persistCurrentModePreference();
    }}

    function clearForm() {{
      document.getElementById("request-label").value = "";
      document.getElementById("scene-draft-text").value = "";
      document.getElementById("source-path").value = "";
      document.getElementById("source-content").value = "";
      document.getElementById("creative-scene-premise").value = "";
      document.getElementById("creative-world-scene").value = "";
      document.getElementById("creative-environment").value = "";
      document.getElementById("creative-styling").value = "";
      document.getElementById("creative-action").value = "";
      document.getElementById("prompt-positive").value = "";
      document.getElementById("prompt-negative").value = "";
      applyActionMessage("");
    }}

    function collectRequestPayload() {{
      return {{
        sourceKind: normalizeText(document.getElementById("source-kind").value),
        endStage: normalizeText(document.getElementById("end-stage").value),
        label: normalizeText(document.getElementById("request-label").value),
        sceneDraftText: document.getElementById("scene-draft-text").value,
        sourcePath: document.getElementById("source-path").value,
        sourceContent: document.getElementById("source-content").value,
        scenePremiseText: document.getElementById("creative-scene-premise").value,
        worldSceneText: document.getElementById("creative-world-scene").value,
        environmentDesignText: document.getElementById("creative-environment").value,
        stylingDesignText: document.getElementById("creative-styling").value,
        actionDesignText: document.getElementById("creative-action").value,
        positivePromptText: document.getElementById("prompt-positive").value,
        negativePromptText: document.getElementById("prompt-negative").value,
      }};
    }}

    function currentEndStageLabel() {{
      const endSelect = document.getElementById("end-stage");
      const option = endSelect.options[endSelect.selectedIndex];
      return normalizeText(option?.text || endSelect.value);
    }}

    async function submitJson(url, payload = null) {{
      const response = await fetch(url, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: payload === null ? "{{}}" : JSON.stringify(payload),
      }});
      const data = await response.json().catch(() => ({{ ok: false, error: "返回结果不是合法 JSON。" }}));
      if (!response.ok || !data.ok) {{
        throw new Error(normalizeText(data.error) || "请求失败。");
      }}
      return data;
    }}

    function renderStatus(snapshot) {{
      const status = snapshot?.status || {{}};
      const permissions = currentPermissions(snapshot);
      const heroStatus = document.getElementById("hero-status");
      heroStatus.textContent = status.statusLabel || "未知";
      heroStatus.className = "pill " + statusClass(status.status);
      document.getElementById("meta-generated").textContent = `最后刷新：${{snapshot.generatedAt || "-"}}`;
      document.getElementById("meta-project").textContent = `项目目录：${{snapshot.projectDir || "-"}}`;
      document.getElementById("status-value").textContent = status.statusLabel || "未知";
      document.getElementById("status-value").className = "status-value " + statusClass(status.status);
      document.getElementById("status-stage").textContent = status.stage || "等待新任务";
      const request = status.request || {{}};
      const requestLabel = normalizeText(request.label) || "未命名任务";
      document.getElementById("status-stage-detail").textContent =
        request.sourceKind ? `起点：${{request.sourceKind}} · 终点：${{request.endStage}} · 标签：${{requestLabel}}` : "当前没有运行中的内容任务。";
      document.getElementById("status-run-id").textContent = `runId：${{status.runId || "-"}}`;
      document.getElementById("status-run-root").textContent = `运行目录：${{status.runRoot || "-"}}`;
      document.getElementById("status-slot").textContent = `执行位：${{status.generationSlotText || "空闲"}}`;
      const statusError = document.getElementById("status-error");
      const shouldShowError = ["failed", "interrupted"].includes(normalizeText(status.status)) && normalizeText(status.error);
      if (shouldShowError) {{
        statusError.style.display = "";
        statusError.textContent = status.error;
      }} else {{
        statusError.style.display = "none";
        statusError.textContent = "";
      }}
      document.getElementById("start-btn").disabled = !status.canStart;
      document.getElementById("stop-btn").disabled = !status.canStop;
      document.getElementById("rerun-btn").disabled = !status.canStart;
      document.getElementById("review-path-btn").hidden = !permissions.allowReviewPath;
      document.getElementById("review-path-input").hidden = !permissions.allowReviewPath;
      document.querySelector(".review-toolbar").hidden = !permissions.allowReviewPath;
    }}

    function historySelectionList(snapshot) {{
      const items = [];
      const seen = new Set();
      const currentRunItem = snapshot?.currentRunItem;
      const history = Array.isArray(snapshot?.history) ? snapshot.history : [];
      if (currentRunItem && !currentRunItem.deleted) {{
        const currentKey = normalizeText(currentRunItem.selectionKey || currentRunItem.runId);
        if (currentKey) {{
          items.push(currentRunItem);
          seen.add(currentKey);
        }}
      }}
      history.forEach((item) => {{
        const key = normalizeText(item.selectionKey || item.runId);
        if (!key || seen.has(key)) return;
        items.push(item);
        seen.add(key);
      }});
      return items;
    }}

    function activeSelectionKey(snapshot) {{
      const currentRunItem = snapshot?.currentRunItem;
      if (currentRunItem) {{
        return normalizeText(currentRunItem.selectionKey || currentRunItem.runId);
      }}
      return "";
    }}

    function suspendDetailRefresh(milliseconds = 6000) {{
      detailSuspendUntil = Math.max(detailSuspendUntil, Date.now() + Math.max(Number(milliseconds) || 0, 0));
    }}

    function shouldRenderDetail(snapshot, options = {{}}) {{
      if (options.forceDetail || !currentSnapshot) {{
        return true;
      }}
      const nextSelection = normalizeText(snapshot?.selectedRunId);
      const previousSelection = normalizeText(currentSnapshot?.selectedRunId);
      if (nextSelection !== previousSelection) {{
        return true;
      }}
      if (!nextSelection) {{
        return false;
      }}
      const activeKey = activeSelectionKey(snapshot);
      if (!activeKey || nextSelection !== activeKey) {{
        return false;
      }}
      if (Date.now() < detailSuspendUntil) {{
        return false;
      }}
      return true;
    }}

    async function moveHistorySelection(step) {{
      const history = historySelectionList(currentSnapshot);
      if (!history.length) return;
      const currentKey = normalizeText(selectedRunId);
      const currentIndex = history.findIndex((item) => normalizeText(item.selectionKey || item.runId) === currentKey);
      let nextIndex = 0;
      if (currentIndex >= 0) {{
        nextIndex = Math.min(Math.max(currentIndex + step, 0), history.length - 1);
      }} else if (step < 0) {{
        nextIndex = history.length - 1;
      }}
      reviewedPath = "";
      reviewedPathDetail = null;
      selectedRunId = normalizeText(history[nextIndex]?.selectionKey || history[nextIndex]?.runId);
      detailSuspendUntil = 0;
      await fetchSnapshot({{ forceDetail: true }});
    }}

    async function jumpHistorySelection(target) {{
      const history = historySelectionList(currentSnapshot);
      if (!history.length) return;
      const index = target === "end" ? history.length - 1 : 0;
      reviewedPath = "";
      reviewedPathDetail = null;
      selectedRunId = normalizeText(history[index]?.selectionKey || history[index]?.runId);
      detailSuspendUntil = 0;
      await fetchSnapshot({{ forceDetail: true }});
    }}

    function renderHistorySummary(snapshot) {{
      const stats = snapshot?.historyStats || {{}};
      const page = snapshot?.historyPage || {{}};
      const showFavorites = hasHistoryFilter(snapshot, "favorites");
      const showDeleted = hasHistoryFilter(snapshot, "deleted");
      const running = Number(stats.running || 0);
      const active = Number(stats.active || 0);
      const deleted = Number(stats.deleted || 0);
      const total = Number(stats.total || 0);
      const loaded = Number(page.loaded || 0);
      const totalFiltered = Number(page.totalFiltered || 0);
      const summaryParts = [`当前 ${{running}}`, `有效 ${{active}}`];
      if (showDeleted) {{
        summaryParts.push(`已删除 ${{deleted}}`);
      }}
      summaryParts.push(`总计 ${{total}}`, `已载入 ${{loaded}}/${{totalFiltered}}`);
      document.getElementById("history-summary").textContent = summaryParts.join(" · ");
      document.getElementById("history-filter-active").classList.toggle("active", historyFilter === "active");
      document.getElementById("history-filter-favorites").classList.toggle("active", historyFilter === "favorites");
      document.getElementById("history-filter-all").classList.toggle("active", historyFilter === "all");
      document.getElementById("history-filter-deleted").classList.toggle("active", historyFilter === "deleted");
      document.getElementById("history-filter-favorites").hidden = !showFavorites;
      document.getElementById("history-filter-deleted").hidden = !showDeleted;
      const loadMoreButton = document.getElementById("history-load-more");
      const hasMore = Boolean(page.hasMore);
      loadMoreButton.hidden = !hasMore;
      loadMoreButton.disabled = !hasMore;
      loadMoreButton.textContent = hasMore ? `加载更多（${{loaded}}/${{totalFiltered}}）` : "已全部载入";
    }}

    function historyListRenderKey(snapshot, history) {{
      return stableJson({{
        selectedRunId: normalizeText(snapshot?.selectedRunId),
        items: (history || []).map((item) => ({{
          selectionKey: normalizeText(item.selectionKey || item.runId),
          runId: normalizeText(item.runId),
          status: normalizeText(item.status),
          deleted: Boolean(item.deleted),
          favorite: Boolean(item.favorite),
          sourceKind: normalizeText(item.sourceKind),
          endStage: normalizeText(item.endStage),
          displayTime: normalizeText(item.displayTime),
          label: normalizeText(item.label),
          sceneDraftPremiseZh: normalizeText(item.sceneDraftPremiseZh),
          error: normalizeText(item.error),
          imageRoute: normalizeText(item.imageRoute),
        }})),
      }});
    }}

    function renderHistory(snapshot) {{
      renderHistorySummary(snapshot);
      const historyRoot = document.getElementById("history-list");
      const history = historySelectionList(snapshot);
      const renderKey = historyListRenderKey(snapshot, history);
      if (renderKey === lastHistoryListRenderKey) {{
        return;
      }}
      lastHistoryListRenderKey = renderKey;

      const renderItems = (items) => items.map((item) => {{
        const selectionKey = item.selectionKey || item.runId || "";
        const isActive = selectionKey && selectionKey === snapshot.selectedRunId;
        const title = item.sceneDraftPremiseZh || item.label || "未命名任务";
        const secondary = `${{decorateSourceKindLabel(item.sourceKind, item.sourceKindLabel || item.sourceKind || "-", snapshot)}} → ${{item.endStageLabel || item.endStage || "-"}}`;
        const errorLine = item.error ? `<div class="muted">错误：${{item.error}}</div>` : "";
        const runIdLine = item.runId ? `<div class="mono muted">runId：${{item.runId}}</div>` : "";
        const timeLabel = item.deleted ? "删除时间" : "记录时间";
        const thumb = item.imageRoute && !item.deleted
          ? `<img class="history-thumb" src="${{item.imageRoute}}" alt="${{title}}" loading="lazy" />`
          : `<div class="history-thumb empty">${{item.deleted ? "已删" : "暂无图"}}</div>`;
        const favoriteBadge = item.favorite ? '<span class="badge">收藏</span>' : "";
        return `
          <li class="history-item${{isActive ? " active" : ""}}${{item.deleted ? " deleted" : ""}}" data-history-select="${{selectionKey}}" tabindex="0">
            <div class="history-main">
              <div>
                <div class="history-top">
                  <div>
                    <div class="history-title">${{title}}</div>
                    <div class="muted">${{secondary}}</div>
                  </div>
                  <span class="badge ${{statusClass(item.status)}}">${{item.statusLabel || item.status || "未知"}}</span>
                </div>
                <div class="history-meta">
                  <div>${{timeLabel}}：${{item.displayTime || "-"}}</div>
                  ${{runIdLine}}
                  ${{errorLine}}
                </div>
              </div>
              <div>${{thumb}}</div>
            </div>
            <div class="history-foot">
              <div class="muted">${{item.deleted ? "目录已删除，索引保留供回看。" : "点击卡片即可切换详情。"}}</div>
            </div>
          </li>
        `;
      }}).join("");

      if (!history.length) {{
        historyRoot.innerHTML = '<li class="empty">当前筛选下没有任务记录。</li>';
      }} else {{
        historyRoot.innerHTML = renderItems(history);
      }}

      document.querySelectorAll("[data-history-select]").forEach((element) => {{
        element.addEventListener("click", (event) => {{
          const key = normalizeText(element.getAttribute("data-history-select"));
          if (!key) return;
          event.preventDefault();
          event.stopPropagation();
          reviewedPath = "";
          reviewedPathDetail = null;
          selectedRunId = key;
          detailSuspendUntil = 0;
          fetchSnapshot({{ forceDetail: true }});
        }});
        element.addEventListener("keydown", (event) => {{
          if (event.key !== "Enter" && event.key !== " ") return;
          const key = normalizeText(element.getAttribute("data-history-select"));
          if (!key) return;
          event.preventDefault();
          reviewedPath = "";
          reviewedPathDetail = null;
          selectedRunId = key;
          detailSuspendUntil = 0;
          fetchSnapshot({{ forceDetail: true }});
        }});
      }});
    }}

    function escapeHtml(value) {{
      return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }}

    function renderMetaRows(rows) {{
      if (!Array.isArray(rows) || !rows.length) return "";
      return `<div class="section-meta">${{rows.map((row) => `<span>${{escapeHtml(row.label)}}：${{escapeHtml(row.value)}}</span>`).join("")}}</div>`;
    }}

    function renderCompareBlocks(section) {{
      const compareBlocks = Array.isArray(section.compareBlocks) ? section.compareBlocks : [];
      if (!compareBlocks.length) return "";
      return `
        <div class="diff-blocks">
          ${{compareBlocks.map((block) => {{
            const variant = normalizeText(block.variant) === "after" ? "after" : "before";
            const segments = Array.isArray(block.segments) ? block.segments : [];
            const contentHtml = segments.length
              ? `<div class="diff-content">${{segments.map((segment) => {{
                  const changedClass = segment.changed ? ` changed ${{variant}}` : "";
                  return `<span class="diff-token${{changedClass}}">${{escapeHtml(segment.text || "")}}</span>`;
                }}).join("")}}</div>`
              : '<div class="empty">当前没有可展示的内容。</div>';
            return `
              <div class="diff-block">
                <div class="diff-title">${{escapeHtml(block.title || "")}}</div>
                ${{contentHtml}}
              </div>
            `;
          }}).join("")}}
        </div>
      `;
    }}

    function renderSection(section, runId) {{
      const rawKey = `${{runId}}:${{section.id}}`;
      const isOpen = expandedRawKeys.has(rawKey);
      const bullets = Array.isArray(section.bullets) ? section.bullets : [];
      const bulletHtml = bullets.length ? `<ul>${{bullets.map((item) => `<li>${{escapeHtml(item)}}</li>`).join("")}}</ul>` : "";
      const compareHtml = renderCompareBlocks(section);
      const rawArea = section.rawText ? `
        <div class="raw-toggle">
          <details data-raw-key="${{escapeHtml(rawKey)}}"${{isOpen ? " open" : ""}}>
            <summary>查看原始文件内容</summary>
            <pre>${{escapeHtml(section.rawText)}}</pre>
          </details>
        </div>
      ` : "";
      const errorText = section.error ? `<div class="muted status-danger">解析提示：${{escapeHtml(section.error)}}</div>` : "";
      const truncatedText = section.truncated ? '<div class="muted">原始内容过长，面板已截断展示。</div>' : "";
      return `
        <article class="section-card" id="section-${{escapeHtml(section.id)}}">
          <h3>${{escapeHtml(section.title)}}</h3>
          <div class="mono muted">${{escapeHtml(section.path || "-")}}</div>
          ${{renderMetaRows(section.metaRows)}}
          ${{compareHtml || (section.bodyText ? `<div class="section-text">${{escapeHtml(section.bodyText)}}</div>` : '<div class="empty">当前没有可展示的正文。</div>')}}
          ${{bulletHtml}}
          ${{errorText}}
          ${{truncatedText}}
          ${{rawArea}}
        </article>
      `;
    }}

    function selectedHistoryItem(snapshot) {{
      const currentKey = normalizeText(snapshot?.selectedRunId);
      return historySelectionList(snapshot).find((item) => normalizeText(item.selectionKey || item.runId) === currentKey) || null;
    }}

    function detailRenderKey(snapshot, detail, selectedItem) {{
      return stableJson({{
        reviewedPath: normalizeText(reviewedPath),
        reviewedPathDetail: reviewedPathDetail || null,
        selectedRunId: normalizeText(snapshot?.selectedRunId),
        busy: Boolean(snapshot?.status?.busy),
        busyRunId: normalizeText(snapshot?.status?.runId),
        selectedItem: selectedItem
          ? {{
              runId: normalizeText(selectedItem.runId),
              selectionKey: normalizeText(selectedItem.selectionKey || selectedItem.runId),
              favorite: Boolean(selectedItem.favorite),
              favoriteKind: normalizeText(selectedItem.favoriteKind),
              deleted: Boolean(selectedItem.deleted),
              deletedAt: normalizeText(selectedItem.deletedAt),
              reviewPath: normalizeText(selectedItem.reviewPath),
              label: normalizeText(selectedItem.label),
              sceneDraftPremiseZh: normalizeText(selectedItem.sceneDraftPremiseZh),
            }}
          : null,
        detail: detail || null,
      }});
    }}

    async function deleteRunById(runId) {{
      if (!runId) return;
      if (!window.confirm(`确认删除这轮任务的整个目录吗？\\n\\n${{runId}}`)) return;
      applyActionMessage("正在删除任务目录…");
      await submitJson("/api/delete-run", {{ runId }});
      if (selectedRunId === runId) {{
        selectedRunId = "";
      }}
      applyActionMessage(`已删除目录：${{runId}}`, "success");
      detailSuspendUntil = 0;
      await fetchSnapshot({{ forceDetail: true }});
    }}

    async function reviewPathDetail() {{
      if (!currentPermissions().allowReviewPath) {{
        applyActionMessage("当前模式不允许审阅本地路径。", "error");
        return;
      }}
      const input = document.getElementById("review-path-input");
      const path = normalizeText(input?.value);
      if (!path) {{
        applyActionMessage("请输入要审阅的目录或文件路径。", "error");
        return;
      }}
      applyActionMessage("正在载入目录审阅…");
      const data = await submitJson("/api/review-path", {{ path }});
      reviewedPath = normalizeText(data.path || path);
      reviewedPathDetail = data.detail || null;
      selectedRunId = "";
      detailSuspendUntil = 0;
      renderDetail(currentSnapshot || {{}});
      applyActionMessage("目录内容已载入。", "success");
    }}

    async function toggleFavorite(payload) {{
      const data = await submitJson("/api/toggle-favorite", payload);
      applyActionMessage(data.favorited ? "已加入收藏。" : "已取消收藏。", "success");
      detailSuspendUntil = 0;
      await fetchSnapshot({{ forceDetail: true }});
    }}

    function renderDetailActions(snapshot, detail, selectedItem) {{
      const root = document.getElementById("detail-actions");
      const permissions = currentPermissions(snapshot);
      const favoriteState = reviewedPathDetail
        ? {{
            favorite: Boolean(reviewedPathDetail?.favorite),
            kind: "path",
            path: normalizeText(reviewedPath || reviewedPathDetail?.reviewPath),
            runId: normalizeText(reviewedPathDetail?.runId),
            runRoot: normalizeText(reviewedPathDetail?.runRoot),
            label: normalizeText(reviewedPathDetail?.detailTitle),
          }}
        : {{
            favorite: Boolean(selectedItem?.favorite),
            kind: normalizeText(selectedItem?.favoriteKind) || "run",
            path: normalizeText(selectedItem?.reviewPath),
            runId: normalizeText(selectedItem?.runId || detail?.runId),
            runRoot: normalizeText(selectedItem?.runRoot || detail?.runRoot),
            label: normalizeText(selectedItem?.sceneDraftPremiseZh || selectedItem?.label || detail?.detailTitle),
            sourceKind: normalizeText(selectedItem?.sourceKind),
            endStage: normalizeText(selectedItem?.endStage),
            sceneDraftPremiseZh: normalizeText(selectedItem?.sceneDraftPremiseZh),
          }};
      const favoriteLabel = favoriteState.favorite ? "取消收藏" : "加入收藏";
      if (reviewedPathDetail) {{
        root.innerHTML = '<button type="button" data-detail-exit-review="1">返回历史</button>';
        root.querySelector("[data-detail-exit-review='1']").addEventListener("click", async () => {{
          clearReviewedPathDetail();
          detailSuspendUntil = 0;
          await fetchSnapshot({{ forceDetail: true }});
        }});
        if (permissions.allowFavorites) {{
          const reviewFavoriteButton = document.createElement("button");
          reviewFavoriteButton.type = "button";
          reviewFavoriteButton.textContent = favoriteLabel;
          reviewFavoriteButton.addEventListener("click", async () => {{
            await toggleFavorite({{
              kind: "path",
              path: favoriteState.path,
              runId: favoriteState.runId,
              runRoot: favoriteState.runRoot,
              label: favoriteState.label,
            }});
          }});
          root.prepend(reviewFavoriteButton);
        }}
        return;
      }}
      const history = historySelectionList(snapshot);
      const currentKey = normalizeText(snapshot?.selectedRunId);
      const index = history.findIndex((item) => normalizeText(item.selectionKey || item.runId) === currentKey);
      const previousItem = index > 0 ? history[index - 1] : null;
      const nextItem = index >= 0 && index < history.length - 1 ? history[index + 1] : null;
      const canDelete = permissions.allowDeleteRun && !!normalizeText(detail?.runId);
      root.innerHTML = `
        <button type="button" data-detail-nav="prev" ${{previousItem ? "" : "disabled"}}>上一条</button>
        <button type="button" data-detail-nav="next" ${{nextItem ? "" : "disabled"}}>下一条</button>
        ${{canDelete ? '<button type="button" class="danger" data-detail-delete="current">删除当前目录</button>' : ""}}
      `;
      if (permissions.allowFavorites) {{
        const favoriteButton = document.createElement("button");
        favoriteButton.type = "button";
        favoriteButton.textContent = favoriteLabel;
        favoriteButton.addEventListener("click", async () => {{
          await toggleFavorite(
            favoriteState.kind === "path" && favoriteState.path
              ? {{
                  kind: "path",
                  path: favoriteState.path,
                  runId: favoriteState.runId,
                  runRoot: favoriteState.runRoot,
                  label: favoriteState.label,
                  sourceKind: favoriteState.sourceKind,
                  endStage: favoriteState.endStage,
                  sceneDraftPremiseZh: favoriteState.sceneDraftPremiseZh,
                }}
              : {{
                  kind: "run",
                  runId: favoriteState.runId,
                  runRoot: favoriteState.runRoot,
                  label: favoriteState.label,
                  sourceKind: favoriteState.sourceKind,
                  endStage: favoriteState.endStage,
                  sceneDraftPremiseZh: favoriteState.sceneDraftPremiseZh,
                }}
          );
        }});
        root.prepend(favoriteButton);
      }}
      root.querySelectorAll("[data-detail-nav]").forEach((button) => {{
        button.addEventListener("click", async () => {{
          const direction = normalizeText(button.getAttribute("data-detail-nav"));
          const target = direction === "prev" ? previousItem : nextItem;
          const key = normalizeText(target?.selectionKey || target?.runId);
          if (!key) return;
          clearReviewedPathDetail();
          selectedRunId = key;
          detailSuspendUntil = 0;
          await fetchSnapshot({{ forceDetail: true }});
        }});
      }});
      const deleteButton = root.querySelector("[data-detail-delete='current']");
      if (deleteButton) {{
        deleteButton.addEventListener("click", async () => {{
          try {{
            await deleteRunById(normalizeText(detail?.runId));
          }} catch (error) {{
            applyActionMessage(error.message || "删除目录失败。", "error");
          }}
        }});
      }}
    }}

    function renderDetail(snapshot) {{
      const detail = reviewedPathDetail || snapshot?.selectedRunDetail;
      const root = document.getElementById("detail-root");
      const badge = document.getElementById("detail-badge");
      const selectedItem = reviewedPathDetail ? null : selectedHistoryItem(snapshot);
      const renderKey = detailRenderKey(snapshot, detail, selectedItem);
      if (renderKey === lastDetailRenderKey) {{
        return;
      }}
      lastDetailRenderKey = renderKey;
      renderDetailActions(snapshot, detail, selectedItem);
      if (!detail) {{
        const status = snapshot?.status || {{}};
        if (selectedItem?.deleted) {{
          badge.textContent = "目录已删除";
          root.className = "";
          root.innerHTML = `
            <div class="detail-summary">
              <div class="history-title">${{escapeHtml(selectedItem.sceneDraftPremiseZh || selectedItem.label || selectedItem.runId || "已删除任务")}}</div>
              <div class="summary-meta">
                <span>runId：${{escapeHtml(selectedItem.runId || "-")}}</span>
                <span>删除时间：${{escapeHtml(selectedItem.deletedAt || selectedItem.displayTime || "-")}}</span>
              </div>
              <div class="muted">该任务目录已经删除，左侧索引项仅用于人工回看与筛选记录。</div>
            </div>
          `;
          return;
        }}
        if (selectedItem?.favorite) {{
          const favoriteKind = normalizeText(selectedItem.favoriteKind);
          const favoriteTitle = selectedItem.sceneDraftPremiseZh || selectedItem.label || (favoriteKind === "path" ? "收藏路径" : "收藏 run");
          const favoriteTargetText = favoriteKind === "path"
            ? (selectedItem.reviewPath || selectedItem.favoriteTarget || "-")
            : (selectedItem.runRoot || selectedItem.runId || "-");
          const favoriteHint = favoriteKind === "path"
            ? "这条收藏当前无法解析出可展示的详情。你可以取消收藏，或修正目标路径后重新审阅。"
            : "这条收藏 run 当前不可用。它通常意味着目录或产物被外部删除了。你可以取消收藏，或恢复目标目录后重新打开。";
          badge.textContent = favoriteKind === "path" ? "收藏路径" : "收藏 run";
          root.className = "";
          root.innerHTML = `
            <div class="detail-summary">
              <div class="history-title">${{escapeHtml(favoriteTitle)}}</div>
              <div class="summary-meta">
                <span>${{favoriteKind === "path" ? "路径" : "目标"}}：${{escapeHtml(favoriteTargetText)}}</span>
                <span>收藏时间：${{escapeHtml(selectedItem.favoriteSavedAt || selectedItem.displayTime || "-")}}</span>
              </div>
              <div class="muted">${{escapeHtml(favoriteHint)}}</div>
            </div>
          `;
          return;
        }}
        if (status.busy) {{
          badge.textContent = "当前任务运行中";
          root.className = "empty";
          root.innerHTML = "当前任务已经启动，正在准备运行目录或等待第一批产物。<br />左侧最上方会保留当前运行项，可随时切回。";
          return;
        }}
        badge.textContent = "未选择任务";
        root.className = "empty";
        root.textContent = "开始一轮任务后，这里会实时展开它的中间产物和最终产物。";
        return;
      }}
      badge.textContent = reviewedPathDetail ? "目录审阅" : (detail.detailTitle || detail.runId || "当前任务");
      const imagePanel = detail.imageRoute
        ? `
          <a class="preview-link" href="${{detail.imageRoute}}" target="_blank" rel="noreferrer">
            <img class="preview-image" src="${{detail.imageRoute}}" alt="${{escapeHtml(detail.detailTitle || detail.runId)}}" />
            <span class="muted">点击查看大图</span>
          </a>
          <span class="preview-path">${{escapeHtml(detail.generatedImagePath || "-")}}</span>
        `
        : '<div class="empty">当前还没有最终图片。</div>';
      const sections = Array.isArray(detail.sections) ? detail.sections : [];
      const sectionsHtml = sections.map((section) => renderSection(section, detail.runId)).join("");
      const sectionNav = sections.length
        ? `
          <div class="section-nav">
            ${{sections.map((section) => `<a href="#section-${{escapeHtml(section.id)}}">${{escapeHtml(section.title)}}</a>`).join("")}}
          </div>
        `
        : "";
      root.className = "";
      root.innerHTML = `
        <div class="detail-hero">
          <div class="detail-summary">
            <div class="history-title">${{escapeHtml(detail.detailTitle || detail.runId)}}</div>
            <div class="summary-meta">
              <span>runId：${{escapeHtml(detail.runId || "-")}}</span>
              <span>运行目录：${{escapeHtml(detail.runRoot || "-")}}</span>
              <span>可用内容：${{detail.sectionCounts?.available || 0}} / ${{detail.sectionCounts?.total || 0}}</span>
            </div>
            <div class="muted">${{escapeHtml(detail.socialPostPreview || "当前还没有社媒文案预览。")}}</div>
            <div class="mono muted">${{escapeHtml(detail.summaryPath || "")}}</div>
          </div>
          <div>${{imagePanel}}</div>
        </div>
        ${{sectionNav}}
        <div class="section-grid" style="margin-top: 18px;">${{sectionsHtml || '<div class="empty">当前没有可展示的中间产物。</div>'}}</div>
      `;
    }}

    async function fetchSnapshot(options = {{}}) {{
      if (snapshotFetchPromise) {{
        if (options.forceDetail) {{
          try {{
            await snapshotFetchPromise;
          }} catch (_error) {{
            // ignore and continue with forced refresh
          }}
        }} else {{
          return snapshotFetchPromise;
        }}
      }}
      const fetchTask = (async () => {{
      rememberExpandedDetails();
      ensureHistoryLimit(currentSnapshot);
      const params = new URLSearchParams();
      if (selectedRunId) {{
        params.set("selectedRunId", selectedRunId);
      }}
      if (historyFilter) {{
        params.set("historyFilter", historyFilter);
      }}
      if (Number(historyLimit) > 0) {{
        params.set("historyLimit", String(historyLimit));
      }}
      const query = params.toString() ? `?${{params.toString()}}` : "";
      const response = await fetch(`/api/snapshot${{query}}`, {{ cache: "no-store" }});
      const snapshot = await response.json();
      if (reviewedPath && options.forceDetail && currentPermissions(snapshot).allowReviewPath) {{
        try {{
          const reviewData = await submitJson("/api/review-path", {{ path: reviewedPath }});
          reviewedPathDetail = reviewData.detail || null;
        }} catch (_error) {{
          reviewedPathDetail = null;
        }}
      }} else if (!currentPermissions(snapshot).allowReviewPath) {{
        clearReviewedPathDetail();
      }}
      ensureHistoryLimit(snapshot);
      if (!hasHistoryFilter(snapshot, historyFilter)) {{
        historyFilter = "active";
      }}
      if (!normalizeText(snapshot?.selectedRunId) && snapshot?.status?.busy) {{
        const activeItem = snapshot?.currentRunItem;
        if (activeItem) {{
          snapshot.selectedRunId = normalizeText(activeItem.selectionKey || activeItem.runId);
        }}
      }}
      const currentActiveKey = activeSelectionKey(snapshot);
      if (normalizeText(snapshot?.selectedRunId) === "__active__" && currentActiveKey && currentActiveKey !== "__active__") {{
        snapshot.selectedRunId = currentActiveKey;
      }}
      const detailWasRendered = shouldRenderDetail(snapshot, options);
      selectedRunId = normalizeText(snapshot?.selectedRunId);
      currentSnapshot = snapshot;
      document.getElementById("hero-title").textContent = snapshot?.identity?.workbenchTitle || "{title_text}";
      ensureFormOptions(snapshot);
      if (!initializedForm) {{
        initializeDefaultForm(snapshot);
        initializedForm = true;
      }}
      renderStatus(snapshot);
      renderHistory(snapshot);
      if (detailWasRendered) {{
        renderDetail(snapshot);
      }}
      }})();
      snapshotFetchPromise = fetchTask;
      try {{
        return await fetchTask;
      }} finally {{
        if (snapshotFetchPromise === fetchTask) {{
          snapshotFetchPromise = null;
        }}
        scheduleSnapshotPoll();
      }}
    }}

    document.getElementById("source-kind").addEventListener("change", () => {{
      updateEndStageOptions(currentSnapshot);
      persistCurrentModePreference();
    }});
    document.getElementById("end-stage").addEventListener("change", () => {{
      persistCurrentModePreference();
    }});
    const detailRoot = document.getElementById("detail-root");
    const reviewToolbar = document.createElement("div");
    reviewToolbar.className = "review-toolbar";
    reviewToolbar.innerHTML = `
      <input id="review-path-input" type="text" placeholder="输入 run 目录、creative 目录或包文件路径，直接调出审阅">
      <button type="button" id="review-path-btn">审阅目录</button>
    `;
    detailRoot.parentNode.insertBefore(reviewToolbar, detailRoot);
    ["wheel", "pointerdown", "focusin"].forEach((eventName) => {{
      detailRoot.addEventListener(eventName, () => {{
        suspendDetailRefresh();
      }});
    }});
    document.getElementById("review-path-btn").addEventListener("click", async () => {{
      await reviewPathDetail();
    }});
    document.getElementById("review-path-input").addEventListener("keydown", async (event) => {{
      if (event.key !== "Enter") return;
      event.preventDefault();
      await reviewPathDetail();
    }});
    document.getElementById("refresh-btn").addEventListener("click", async () => {{
      detailSuspendUntil = 0;
      await fetchSnapshot({{ forceDetail: true }});
    }});
    document.addEventListener("visibilitychange", () => {{
      if (!document.hidden) {{
        detailSuspendUntil = 0;
        fetchSnapshot().catch(() => null);
      }}
    }});
    document.getElementById("history-filter-active").addEventListener("click", async () => {{
      historyFilter = "active";
      historyLimit = configuredHistoryLimit(currentSnapshot);
      detailSuspendUntil = 0;
      await fetchSnapshot({{ forceDetail: true }});
    }});
    document.getElementById("history-filter-favorites").addEventListener("click", async () => {{
      historyFilter = "favorites";
      historyLimit = configuredHistoryLimit(currentSnapshot);
      detailSuspendUntil = 0;
      await fetchSnapshot({{ forceDetail: true }});
    }});
    document.getElementById("history-filter-all").addEventListener("click", async () => {{
      historyFilter = "all";
      historyLimit = configuredHistoryLimit(currentSnapshot);
      detailSuspendUntil = 0;
      await fetchSnapshot({{ forceDetail: true }});
    }});
    document.getElementById("history-filter-deleted").addEventListener("click", async () => {{
      historyFilter = "deleted";
      historyLimit = configuredHistoryLimit(currentSnapshot);
      detailSuspendUntil = 0;
      await fetchSnapshot({{ forceDetail: true }});
    }});
    document.getElementById("history-load-more").addEventListener("click", async () => {{
      historyLimit = Number(historyLimit || 0) + configuredHistoryLimit(currentSnapshot);
      detailSuspendUntil = 0;
      await fetchSnapshot({{ forceDetail: true }});
    }});
    document.getElementById("fill-last-btn").addEventListener("click", () => {{
      applyRequestToForm(currentSnapshot?.lastRequest || {{}});
      applyActionMessage("已载入上一次请求。", "success");
    }});
    document.getElementById("clear-form-btn").addEventListener("click", () => {{
      clearForm();
      applyActionMessage("输入区已清空。", "success");
    }});
    document.getElementById("start-btn").addEventListener("click", async () => {{
      try {{
        applyActionMessage("正在启动任务…");
        await submitJson("/api/start", collectRequestPayload());
        clearReviewedPathDetail();
        selectedRunId = "__active__";
        applyActionMessage("任务已启动。", "success");
        detailSuspendUntil = 0;
        await fetchSnapshot({{ forceDetail: true }});
      }} catch (error) {{
        applyActionMessage(error.message || "启动任务失败。", "error");
      }}
    }});
    document.getElementById("stop-btn").addEventListener("click", async () => {{
      try {{
        applyActionMessage("正在请求停止当前任务…");
        const data = await submitJson("/api/stop");
        applyActionMessage(data.alreadyStopping ? "停止请求已在处理中。" : "已发送停止请求。", "success");
        detailSuspendUntil = 0;
        await fetchSnapshot({{ forceDetail: true }});
      }} catch (error) {{
        applyActionMessage(error.message || "停止任务失败。", "error");
      }}
    }});
    document.getElementById("rerun-btn").addEventListener("click", async () => {{
      try {{
        applyActionMessage("正在复跑上一轮请求…");
        await submitJson("/api/rerun-last");
        clearReviewedPathDetail();
        selectedRunId = "__active__";
        applyActionMessage("已开始复跑上一轮任务。", "success");
        detailSuspendUntil = 0;
        await fetchSnapshot({{ forceDetail: true }});
      }} catch (error) {{
        applyActionMessage(error.message || "复跑失败。", "error");
      }}
    }});
    document.addEventListener("keydown", async (event) => {{
      const target = event.target;
      const tagName = String(target?.tagName || "").toLowerCase();
      const isEditing =
        tagName === "input" ||
        tagName === "textarea" ||
        tagName === "select" ||
        Boolean(target?.isContentEditable);
      if (isEditing || event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key === "ArrowUp") {{
        event.preventDefault();
        await moveHistorySelection(-1);
      }} else if (event.key === "ArrowDown") {{
        event.preventDefault();
        await moveHistorySelection(1);
      }} else if (event.key === "Home") {{
        event.preventDefault();
        await jumpHistorySelection("start");
      }} else if (event.key === "End") {{
        event.preventDefault();
        await jumpHistorySelection("end");
      }}
    }});

    fetchSnapshot().catch((error) => {{
      applyActionMessage(error.message || "读取面板状态失败。", "error");
    }});
  </script>
</body>
</html>"""
