from __future__ import annotations

import json


def render_dashboard_html(*, project_name: str, refresh_seconds: int) -> str:
    refresh_ms = max(int(refresh_seconds), 2) * 1000
    refresh_label = max(int(refresh_seconds), 2)
    title_text = project_name if str(project_name).endswith("运维面板") else f"{project_name} 运维面板"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_text}</title>
  <style>
    :root {{
      --bg: #f4f1ea;
      --panel: #fffdf8;
      --ink: #1f2933;
      --muted: #66727f;
      --line: #ddd4c7;
      --accent: #2f6f63;
      --accent-soft: #d8ece7;
      --warn: #c66a2b;
      --danger: #b84c38;
      --shadow: 0 14px 32px rgba(35, 40, 47, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(47, 111, 99, 0.08), transparent 32%),
        linear-gradient(180deg, #f7f4ee 0%, var(--bg) 100%);
      min-height: 100vh;
    }}
    .page {{
      width: min(1440px, calc(100vw - 32px));
      margin: 24px auto 40px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(47, 111, 99, 0.96), rgba(37, 55, 71, 0.96));
      color: #f7faf9;
      padding: 24px 28px;
      border-radius: 24px;
      box-shadow: var(--shadow);
      display: grid;
      gap: 14px;
    }}
    .hero-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
    }}
    h1 {{
      margin: 0;
      font-size: 28px;
      line-height: 1.15;
    }}
    .hero-sub {{
      color: rgba(247, 250, 249, 0.86);
      font-size: 14px;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 9px 14px;
      background: rgba(255, 255, 255, 0.14);
      font-size: 13px;
      font-weight: 600;
    }}
    .toolbar {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
    }}
    button {{
      appearance: none;
      border: 0;
      border-radius: 999px;
      padding: 10px 16px;
      background: #f7faf9;
      color: var(--accent);
      font-weight: 700;
      cursor: pointer;
    }}
    .meta {{
      display: flex;
      gap: 18px;
      flex-wrap: wrap;
      color: rgba(247, 250, 249, 0.88);
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
      padding: 18px 18px 16px;
      box-shadow: var(--shadow);
      min-height: 160px;
    }}
    .card h2 {{
      margin: 0 0 12px;
      font-size: 16px;
    }}
    .span-3 {{ grid-column: span 3; }}
    .span-4 {{ grid-column: span 4; }}
    .span-6 {{ grid-column: span 6; }}
    .span-8 {{ grid-column: span 8; }}
    .span-12 {{ grid-column: span 12; }}
    .stats {{
      display: grid;
      gap: 10px;
    }}
    .stat-value {{
      font-size: 28px;
      font-weight: 700;
      line-height: 1;
    }}
    .muted {{ color: var(--muted); }}
    .status-ok {{ color: var(--accent); }}
    .status-warn {{ color: var(--warn); }}
    .status-danger {{ color: var(--danger); }}
    .list {{
      display: grid;
      gap: 10px;
      margin: 0;
      padding: 0;
      list-style: none;
    }}
    .list-item {{
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px 14px;
      background: rgba(255, 255, 255, 0.64);
    }}
    .list-item strong {{
      display: block;
      margin-bottom: 6px;
    }}
    .preview-link {{
      display: inline-flex;
      flex-direction: column;
      gap: 8px;
      color: inherit;
      text-decoration: none;
    }}
    .action-link {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: var(--accent);
      font-weight: 700;
      text-decoration: none;
      margin-top: 8px;
    }}
    .preview-image {{
      width: 100%;
      max-width: 280px;
      aspect-ratio: 1 / 1;
      object-fit: cover;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, #f7f4ee 0%, #efe8dd 100%);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      padding: 10px 8px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{ color: var(--muted); font-weight: 600; }}
    .mono {{
      font-family: ui-monospace, "Cascadia Mono", Consolas, monospace;
      font-size: 12px;
      word-break: break-all;
    }}
    pre {{
      margin: 0;
      border-radius: 14px;
      padding: 14px;
      background: #1d2430;
      color: #f3f6f9;
      font-family: ui-monospace, "Cascadia Mono", Consolas, monospace;
      font-size: 12px;
      overflow: auto;
      max-height: 320px;
    }}
    .empty {{
      color: var(--muted);
      padding: 10px 0;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 12px;
      font-weight: 700;
      background: var(--accent-soft);
      color: var(--accent);
    }}
    @media (max-width: 1100px) {{
      .span-3, .span-4, .span-6, .span-8 {{ grid-column: span 12; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <div class="hero-top">
        <div>
          <h1 id="hero-title">{title_text}</h1>
          <div class="hero-sub">只读优先，本地观察 QQ 服务、队列、采样健康和最近产物。</div>
        </div>
        <div class="toolbar">
          <div class="pill" id="service-pill">正在读取状态</div>
          <button type="button" id="refresh-btn">立即刷新</button>
        </div>
      </div>
      <div class="meta">
        <span id="meta-generated">最后刷新：-</span>
        <span id="meta-project">项目目录：-</span>
        <span>自动刷新：每 {refresh_label} 秒</span>
      </div>
    </section>

    <div class="grid">
      <section class="card span-3">
        <h2>服务状态</h2>
        <div class="stats">
          <div class="stat-value" id="service-status-value">-</div>
          <div id="service-stage" class="muted">-</div>
          <div id="service-summary" class="muted">-</div>
        </div>
      </section>

      <section class="card span-3">
        <h2>当前运行</h2>
        <div class="stats">
          <div class="stat-value" id="active-run-id">-</div>
          <div id="active-user" class="muted">-</div>
          <div id="active-error" class="muted">-</div>
          <div id="active-detail-link"></div>
        </div>
      </section>

      <section class="card span-3">
        <h2>队列概览</h2>
        <div class="stats">
          <div class="stat-value" id="queue-counts">-</div>
          <div id="queue-hint" class="muted">-</div>
        </div>
      </section>

      <section class="card span-3">
        <h2>采样健康</h2>
        <div class="stats">
          <div class="stat-value" id="sampling-status">-</div>
          <div id="sampling-last-source" class="muted">-</div>
          <div id="sampling-backoff" class="muted">-</div>
        </div>
      </section>

      <section class="card span-8">
        <h2>待处理队列</h2>
        <div id="pending-jobs"></div>
      </section>

      <section class="card span-4">
        <h2>正在运行的任务</h2>
        <div id="running-jobs"></div>
      </section>

      <section class="card span-6">
        <h2>最近任务结果</h2>
        <div id="recent-jobs"></div>
      </section>

      <section class="card span-6">
        <h2>最近成功产物</h2>
        <div id="recent-runs"></div>
      </section>

      <section class="card span-6">
        <h2>事件流</h2>
        <div id="events"></div>
      </section>

      <section class="card span-6">
        <h2>采样告警</h2>
        <div id="sampling-alerts"></div>
      </section>

      <section class="card span-6">
        <h2>stdout 尾部</h2>
        <pre id="stdout-tail">等待数据…</pre>
      </section>

      <section class="card span-6">
        <h2>stderr 尾部</h2>
        <pre id="stderr-tail">等待数据…</pre>
      </section>

      <section class="card span-12">
        <h2>常用命令与路径</h2>
        <div id="commands"></div>
      </section>
    </div>
  </div>

  <script>
    const REFRESH_MS = {refresh_ms};

    function escapeHtml(value) {{
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }}

    function text(value, fallback = "—") {{
      const normalized = String(value ?? "").trim();
      return normalized || fallback;
    }}

    function joinLines(items, fallback = "暂无数据") {{
      if (!Array.isArray(items) || items.length === 0) {{
        return fallback;
      }}
      return items.join("\\n");
    }}

    function renderSimpleList(containerId, items, renderItem, emptyText) {{
      const container = document.getElementById(containerId);
      if (!Array.isArray(items) || items.length === 0) {{
        container.innerHTML = `<div class="empty">${{escapeHtml(emptyText)}}</div>`;
        return;
      }}
      container.innerHTML = `<ul class="list">${{items.map(renderItem).join("")}}</ul>`;
    }}

    function renderTable(containerId, headers, rows, emptyText) {{
      const container = document.getElementById(containerId);
      if (!Array.isArray(rows) || rows.length === 0) {{
        container.innerHTML = `<div class="empty">${{escapeHtml(emptyText)}}</div>`;
        return;
      }}
      const headHtml = headers.map((header) => `<th>${{escapeHtml(header)}}</th>`).join("");
      const rowHtml = rows.map((cells) => `<tr>${{cells.map((cell) => `<td>${{cell}}</td>`).join("")}}</tr>`).join("");
      container.innerHTML = `<table><thead><tr>${{headHtml}}</tr></thead><tbody>${{rowHtml}}</tbody></table>`;
    }}

    async function submitJson(path, payload) {{
      const response = await fetch(path, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(payload || {{}}),
      }});
      const data = await response.json().catch(() => ({{ ok: false, error: `HTTP ${{response.status}}` }}));
      if (!response.ok || data.ok === false) {{
        throw new Error(text(data.error, `HTTP ${{response.status}}`));
      }}
      return data;
    }}

    async function toggleFavorite(payload) {{
      await submitJson("/api/toggle-favorite", payload);
      await loadSnapshot();
    }}

    function serviceTone(service) {{
      if (!service) return "status-warn";
      if (service.running && ["listening", "running", "starting"].includes(service.status)) return "status-ok";
      if (service.status === "reconnecting" || service.status === "stopping") return "status-warn";
      if (service.status === "error" || service.staleLock) return "status-danger";
      return "status-warn";
    }}

    function renderSnapshot(data) {{
      const service = data.service || {{}};
      const queue = data.queue || {{}};
      const sampling = data.sampling || {{}};
      const identity = data.identity || {{}};

      document.getElementById("meta-generated").textContent = `最后刷新：${{text(data.generatedAt)}}`;
      document.getElementById("meta-project").textContent = `项目目录：${{text(data.projectDir)}}`;
      const dashboardTitle = text(identity.dashboardTitle, "{title_text}");
      document.title = dashboardTitle;
      document.getElementById("hero-title").textContent = dashboardTitle;

      const servicePill = document.getElementById("service-pill");
      servicePill.textContent = `${{text(service.statusLabel)}} / ${{text(service.stageLabel)}}`;
      servicePill.className = `pill ${{serviceTone(service)}}`;

      const statusValue = document.getElementById("service-status-value");
      statusValue.textContent = text(service.statusLabel);
      statusValue.className = `stat-value ${{serviceTone(service)}}`;

      document.getElementById("service-stage").textContent = `阶段：${{text(service.stageLabel)}}`;
      document.getElementById("service-summary").textContent =
        `PID：${{text(service.pid)}} | 锁：${{service.staleLock ? "残留" : "正常"}} | 状态更新时间：${{text(service.updatedAt)}}`;

      document.getElementById("active-run-id").textContent = text(service.runId, "当前无运行任务");
      document.getElementById("active-user").textContent =
        `用户：${{text(service.userOpenIdMasked)}} | 排队：${{text(service.queuedCount, "0")}}`;
      document.getElementById("active-error").textContent =
        service.error ? `最近错误：${{service.error}}` : "当前无明显错误摘要";
      document.getElementById("active-detail-link").innerHTML = service.runDetailRoute
        ? `<a class="action-link" href="${{escapeHtml(text(service.runDetailRoute))}}">查看当前内容详情</a>`
        : "";

      document.getElementById("queue-counts").textContent =
        `${{text(queue.pendingCount, "0")}} 等待 / ${{text(queue.runningCount, "0")}} 运行`;
      document.getElementById("queue-hint").textContent =
        queue.error ? `队列读取异常：${{queue.error}}` : `队列库：${{text(queue.dbPath)}}`;

      document.getElementById("sampling-status").textContent =
        sampling.available ? "已接入" : "暂无健康文件";
      document.getElementById("sampling-last-source").textContent =
        sampling.lastSample && sampling.lastSample.providerZh
          ? `最近样本：${{sampling.lastSample.providerZh}}`
          : "最近没有有效外部样本记录";
      document.getElementById("sampling-backoff").textContent =
        `Backoff：源 ${{(sampling.activeSourceBackoffs || []).length}} / 分区 ${{(sampling.activePartitionBackoffs || []).length}}`;

      renderTable(
        "pending-jobs",
        ["队列", "用户", "类型", "模式", "提交时间"],
        (queue.pendingJobs || []).map((item) => [
          escapeHtml(`#${{text(item.queuePosition, "0")}}`),
          escapeHtml(text(item.userOpenIdMasked)),
          escapeHtml(text(item.jobKind)),
          escapeHtml(text(item.mode)),
          `<span class="mono">${{escapeHtml(text(item.createdAt))}}</span>`,
        ]),
        "当前没有待处理任务。",
      );

      renderSimpleList(
        "running-jobs",
        queue.runningJobs || [],
        (item) => `
          <li class="list-item">
            <strong>${{escapeHtml(text(item.userOpenIdMasked))}} / ${{escapeHtml(text(item.jobKind))}}</strong>
            <div>模式：${{escapeHtml(text(item.mode))}}</div>
            <div>开始：<span class="mono">${{escapeHtml(text(item.startedAt))}}</span></div>
            <div>runId：<span class="mono">${{escapeHtml(text(item.runId))}}</span></div>
          </li>
        `,
        "当前没有运行中的任务。",
      );

      renderTable(
        "recent-jobs",
        ["状态", "用户", "类型", "runId", "错误摘要"],
        (queue.recentJobs || []).map((item) => [
          `<span class="badge">${{escapeHtml(text(item.status))}}</span>`,
          escapeHtml(text(item.userOpenIdMasked)),
          escapeHtml(text(item.jobKind)),
          `<span class="mono">${{escapeHtml(text(item.runId))}}</span>`,
          escapeHtml(text(item.error)),
        ]),
        "最近还没有已完成或失败的任务记录。",
      );

      renderSimpleList(
        "recent-runs",
        data.recentRuns || [],
        (item) => `
          <li class="list-item">
            ${{
              item.generatedImagePath
                ? `<a class="preview-link" href="${{escapeHtml(text(item.imageRoute))}}" target="_blank" rel="noreferrer">
                     <img class="preview-image" src="${{escapeHtml(text(item.imageRoute))}}" alt="${{escapeHtml(text(item.sceneDraftPremiseZh, item.runId))}}" loading="lazy">
                     <strong>${{escapeHtml(text(item.sceneDraftPremiseZh, item.runId))}}</strong>
                   </a>`
                : `<strong>${{escapeHtml(text(item.sceneDraftPremiseZh, item.runId))}}</strong>`
            }}
            <div class="mono">${{escapeHtml(text(item.runId))}}</div>
            <div>${{escapeHtml(text(item.socialPostPreview, "无社媒文案预览"))}}</div>
            <div class="muted">发布时间：${{escapeHtml(text(item.publishedAt, "未记录"))}}</div>
            <div>${{item.favorite ? '<span class="badge">收藏</span>' : ""}}</div>
            <button
              type="button"
              data-toggle-favorite-run="${{escapeHtml(text(item.runId))}}"
              data-run-root="${{escapeHtml(text(item.runRoot))}}"
              data-scene-title="${{escapeHtml(text(item.sceneDraftPremiseZh))}}">
              ${{item.favorite ? "取消收藏" : "加入收藏"}}
            </button>
            <a class="action-link" href="${{escapeHtml(text(item.detailRoute, '#'))}}">查看内容详情</a>
          </li>
        `,
        "最近没有成功产物。",
      );
      document.querySelectorAll("[data-toggle-favorite-run]").forEach((button) => {{
        button.addEventListener("click", async () => {{
          button.disabled = true;
          try {{
            await toggleFavorite({{
              kind: "run",
              runId: text(button.getAttribute("data-toggle-favorite-run"), ""),
              runRoot: text(button.getAttribute("data-run-root"), ""),
              label: text(button.getAttribute("data-scene-title"), ""),
              sceneDraftPremiseZh: text(button.getAttribute("data-scene-title"), ""),
            }});
          }} catch (error) {{
            button.disabled = false;
            throw error;
          }}
        }});
      }});

      renderSimpleList(
        "events",
        data.events || [],
        (item) => `
          <li class="list-item">
            <strong>${{escapeHtml(text(item.type))}}</strong>
            <div class="mono">${{escapeHtml(text(item.recordedAt))}}</div>
            <div>${{escapeHtml(text(item.message || item.error || item.reason || item.stageLabel))}}</div>
          </li>
        `,
        "最近没有事件流水。",
      );

      const samplingAlerts = [];
      for (const item of (sampling.activeSourceBackoffs || [])) {{
        samplingAlerts.push(`
          <li class="list-item">
            <strong>源退避：${{escapeHtml(text(item.sourceKey))}}</strong>
            <div class="mono">${{escapeHtml(text(item.blockedUntil))}}</div>
            <div>${{escapeHtml(text(item.lastError))}}</div>
          </li>
        `);
      }}
      for (const item of (sampling.activePartitionBackoffs || [])) {{
        samplingAlerts.push(`
          <li class="list-item">
            <strong>分区退避：${{escapeHtml(text(item.providerKey))}}</strong>
            <div class="mono">${{escapeHtml(text(item.blockedUntil))}}</div>
            <div>${{escapeHtml(text(item.lastError))}}</div>
          </li>
        `);
      }}
      for (const item of (sampling.topFailingPartitions || [])) {{
        samplingAlerts.push(`
          <li class="list-item">
            <strong>${{escapeHtml(text(item.providerZh, item.providerKey))}}</strong>
            <div>连续失败：${{escapeHtml(text(item.consecutiveFailures, "0"))}} / 总失败：${{escapeHtml(text(item.failureCount, "0"))}}</div>
            <div>${{escapeHtml(text(item.lastError))}}</div>
          </li>
        `);
      }}
      if (samplingAlerts.length === 0) {{
        document.getElementById("sampling-alerts").innerHTML = '<div class="empty">当前没有明显采样告警。</div>';
      }} else {{
        document.getElementById("sampling-alerts").innerHTML = `<ul class="list">${{samplingAlerts.join("")}}</ul>`;
      }}

      document.getElementById("stdout-tail").textContent = joinLines(data.logs?.stdoutTail || [], "stdout 还没有输出。");
      document.getElementById("stderr-tail").textContent = joinLines(data.logs?.stderrTail || [], "stderr 还没有输出。");

      renderSimpleList(
        "commands",
        [
          `面板启动：${{text(data.commands?.dashboardStart)}}`,
          `服务状态：${{text(data.commands?.serviceStatus)}}`,
          `服务重启：${{text(data.commands?.serviceRestart)}}`,
          `stdout：${{text(data.logs?.stdoutPath)}}`,
          `stderr：${{text(data.logs?.stderrPath)}}`,
          `events：${{text(data.service?.eventsPath)}}`,
        ],
        (item) => `<li class="list-item mono">${{escapeHtml(item)}}</li>`,
        "暂无命令信息。",
      );
    }}

    async function loadSnapshot() {{
      try {{
        const response = await fetch("/api/snapshot", {{ cache: "no-store" }});
        if (!response.ok) {{
          throw new Error(`HTTP ${{response.status}}`);
        }}
        const data = await response.json();
        renderSnapshot(data);
      }} catch (error) {{
        document.getElementById("service-pill").textContent = `读取失败：${{error.message}}`;
        document.getElementById("service-pill").className = "pill status-danger";
      }}
    }}

    document.getElementById("refresh-btn").addEventListener("click", loadSnapshot);
    loadSnapshot();
    window.setInterval(loadSnapshot, REFRESH_MS);
  </script>
</body>
</html>
"""


def render_run_detail_html(*, project_name: str, run_id: str, refresh_seconds: int) -> str:
    refresh_ms = max(int(refresh_seconds), 2) * 1000
    title_text = f"{project_name} / {run_id}"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_text}</title>
  <style>
    :root {{
      --bg: #f4f1ea;
      --panel: #fffdf8;
      --ink: #1f2933;
      --muted: #66727f;
      --line: #ddd4c7;
      --accent: #2f6f63;
      --accent-soft: #d8ece7;
      --warn: #c66a2b;
      --danger: #b84c38;
      --shadow: 0 14px 32px rgba(35, 40, 47, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(47, 111, 99, 0.08), transparent 32%),
        linear-gradient(180deg, #f7f4ee 0%, var(--bg) 100%);
      min-height: 100vh;
    }}
    .page {{
      width: min(1440px, calc(100vw - 32px));
      margin: 24px auto 40px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(47, 111, 99, 0.96), rgba(37, 55, 71, 0.96));
      color: #f7faf9;
      padding: 24px 28px;
      border-radius: 24px;
      box-shadow: var(--shadow);
      display: grid;
      gap: 14px;
    }}
    .hero-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
    }}
    h1 {{
      margin: 0;
      font-size: 28px;
      line-height: 1.15;
    }}
    .hero-sub {{
      color: rgba(247, 250, 249, 0.86);
      font-size: 14px;
    }}
    .toolbar {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 9px 14px;
      background: rgba(255, 255, 255, 0.14);
      font-size: 13px;
      font-weight: 600;
      color: #f7faf9;
      text-decoration: none;
    }}
    button {{
      appearance: none;
      border: 0;
      border-radius: 999px;
      padding: 10px 16px;
      background: #f7faf9;
      color: var(--accent);
      font-weight: 700;
      cursor: pointer;
    }}
    .meta {{
      display: flex;
      gap: 18px;
      flex-wrap: wrap;
      color: rgba(247, 250, 249, 0.88);
      font-size: 13px;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 320px;
      gap: 16px;
      margin-top: 18px;
      align-items: start;
    }}
    .stack {{
      display: grid;
      gap: 16px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 18px 18px 16px;
      box-shadow: var(--shadow);
    }}
    .card h2 {{
      margin: 0 0 12px;
      font-size: 16px;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
    }}
    .stat-value {{
      font-size: 24px;
      font-weight: 700;
      line-height: 1.1;
    }}
    .muted {{ color: var(--muted); }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 12px;
      font-weight: 700;
      background: var(--accent-soft);
      color: var(--accent);
    }}
    .badge.warn {{
      background: #f8e4d4;
      color: var(--warn);
    }}
    .badge.danger {{
      background: #f4d7d2;
      color: var(--danger);
    }}
    .section-nav {{
      display: grid;
      gap: 10px;
      position: sticky;
      top: 24px;
    }}
    .section-nav-links {{
      display: grid;
      gap: 10px;
    }}
    .section-nav a {{
      display: block;
      text-decoration: none;
      color: var(--accent);
      font-weight: 700;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 10px 12px;
      background: rgba(255, 255, 255, 0.64);
      line-height: 1.4;
      word-break: break-word;
    }}
    .doc-block {{
      white-space: pre-wrap;
      line-height: 1.6;
      background: rgba(255, 255, 255, 0.76);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      font-size: 14px;
    }}
    .meta-table {{
      display: grid;
      gap: 8px;
      margin-bottom: 14px;
    }}
    .meta-row {{
      display: grid;
      grid-template-columns: 88px 1fr;
      gap: 12px;
      align-items: start;
      font-size: 14px;
    }}
    .meta-label {{
      color: var(--muted);
      font-weight: 700;
    }}
    .bullet-list {{
      margin: 0 0 14px 18px;
      padding: 0;
      display: grid;
      gap: 8px;
    }}
    .preview-image {{
      width: 100%;
      max-width: 360px;
      aspect-ratio: 1 / 1;
      object-fit: cover;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, #f7f4ee 0%, #efe8dd 100%);
    }}
    .preview-path {{
      display: block;
      margin-top: 8px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.5;
      word-break: break-all;
    }}
    .action-link {{
      color: var(--accent);
      font-weight: 700;
      text-decoration: none;
    }}
    details {{
      margin-top: 14px;
      border-top: 1px dashed var(--line);
      padding-top: 14px;
    }}
    summary {{
      cursor: pointer;
      font-weight: 700;
      color: var(--accent);
    }}
    .empty {{
      color: var(--muted);
      padding: 10px 0;
    }}
    .mono {{
      font-family: ui-monospace, "Cascadia Mono", Consolas, monospace;
      font-size: 12px;
      word-break: break-all;
    }}
    .diff-blocks {{
      display: grid;
      gap: 14px;
    }}
    .diff-block {{
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.76);
      overflow: hidden;
    }}
    .diff-title {{
      padding: 10px 14px;
      font-weight: 700;
      color: var(--accent);
      border-bottom: 1px solid var(--line);
      background: rgba(47, 111, 99, 0.06);
    }}
    .diff-content {{
      padding: 14px;
      line-height: 1.8;
      display: flex;
      flex-wrap: wrap;
      gap: 8px 6px;
    }}
    .diff-token {{
      display: inline-flex;
      align-items: center;
      padding: 3px 8px;
      border-radius: 999px;
      background: rgba(31, 41, 51, 0.06);
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .diff-token.changed.before {{
      background: rgba(184, 76, 56, 0.14);
      color: var(--danger);
      border: 1px solid rgba(184, 76, 56, 0.22);
    }}
    .diff-token.changed.after {{
      background: rgba(47, 111, 99, 0.14);
      color: var(--accent);
      border: 1px solid rgba(47, 111, 99, 0.22);
    }}
    @media (max-width: 1100px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
      .summary-grid {{
        grid-template-columns: 1fr;
      }}
      .section-nav {{
        position: static;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <div class="hero-top">
        <div>
          <h1 id="detail-title">{title_text}</h1>
          <div class="hero-sub">按 run 查看采样原始内容、设计稿链路，以及最终送给生图基座的 Prompt。</div>
        </div>
        <div class="toolbar">
          <a class="pill" href="/">返回首页</a>
          <button type="button" id="favorite-btn">加入收藏</button>
          <button type="button" id="refresh-btn">立即刷新</button>
        </div>
      </div>
      <div class="meta">
        <span id="meta-run-id">runId：{run_id}</span>
        <span id="meta-run-root">运行目录：-</span>
        <span id="meta-generated">最后刷新：-</span>
      </div>
    </section>

    <div class="layout">
      <main class="stack">
        <section class="card">
          <h2>内容链概览</h2>
          <div class="summary-grid">
            <div>
              <div class="stat-value" id="summary-premise">-</div>
              <div class="muted" id="summary-publish">-</div>
            </div>
            <div>
              <div class="stat-value" id="summary-sections">-</div>
              <div class="muted" id="summary-social-post">-</div>
            </div>
            <div id="summary-image-block">
              <div class="muted">当前没有可预览的生成图。</div>
            </div>
          </div>
        </section>

        <div id="detail-sections" class="stack"></div>
      </main>

      <aside class="stack">
        <section class="card section-nav">
          <h2>快速定位</h2>
          <div id="section-nav" class="section-nav-links"></div>
        </section>
      </aside>
    </div>
  </div>

  <script>
    const RUN_ID = {json.dumps(run_id, ensure_ascii=False)};
    const REFRESH_MS = {refresh_ms};
    let currentDetailSnapshot = null;

    function escapeHtml(value) {{
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }}

    function text(value, fallback = "—") {{
      const normalized = String(value ?? "").trim();
      return normalized || fallback;
    }}

    function sectionTone(section) {{
      if (!section.exists) return "danger";
      if (section.error) return "warn";
      if (section.truncated) return "warn";
      return "";
    }}

    function sectionStatusText(section) {{
      if (!section.exists) return "缺失";
      if (section.error) return "需留意";
      if (section.truncated) return "已截断";
      return "正常";
    }}

    function renderSection(section, expandedRawKeys) {{
      const badgeTone = sectionTone(section);
      const metaRows = Array.isArray(section.metaRows) ? section.metaRows : [];
      const bullets = Array.isArray(section.bullets) ? section.bullets : [];
      const hasRaw = section.rawText && section.rawText !== section.bodyText;
      const rawKey = `${{text(section.id, "section")}}-raw`;
      const rawOpen = expandedRawKeys.has(rawKey) ? " open" : "";
      const metaHtml = metaRows.length
        ? `<div class="meta-table">${{metaRows.map((row) => `
            <div class="meta-row">
              <div class="meta-label">${{escapeHtml(text(row.label))}}</div>
              <div>${{escapeHtml(text(row.value))}}</div>
            </div>
          `).join("")}}</div>`
        : "";
      const bulletHtml = bullets.length
        ? `<ul class="bullet-list">${{bullets.map((item) => `<li>${{escapeHtml(item)}}</li>`).join("")}}</ul>`
        : "";
      const errorHtml = section.error
        ? `<div class="empty">读取提示：${{escapeHtml(section.error)}}</div>`
        : "";
      const bodyHtml = section.exists
        ? `<div class="doc-block">${{escapeHtml(text(section.bodyText, "文件存在，但当前没有可展示内容。"))}}</div>`
        : `<div class="empty">当前 run 中没有这份文件。</div>`;
      const rawHtml = hasRaw
        ? `<details data-raw-key="${{escapeHtml(rawKey)}}"${{rawOpen}}><summary>查看原始文件内容</summary><div class="doc-block mono">${{escapeHtml(section.rawText)}}</div></details>`
        : "";
      return `
        <section class="card" id="${{escapeHtml(section.id)}}">
          <h2>${{escapeHtml(text(section.title))}} <span class="badge ${{badgeTone}}">${{escapeHtml(sectionStatusText(section))}}</span></h2>
          <div class="muted mono">${{escapeHtml(text(section.path))}}</div>
          ${{metaHtml}}
          ${{bulletHtml}}
          ${{errorHtml}}
          ${{bodyHtml}}
          ${{rawHtml}}
        </section>
      `;
    }}

    async function submitJson(path, payload) {{
      const response = await fetch(path, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(payload || {{}}),
      }});
      const data = await response.json().catch(() => ({{ ok: false, error: `HTTP ${{response.status}}` }}));
      if (!response.ok || data.ok === false) {{
        throw new Error(text(data.error, `HTTP ${{response.status}}`));
      }}
      return data;
    }}

    function renderSnapshot(data) {{
      currentDetailSnapshot = data;
      document.title = `${{text(data.identity?.dashboardTitle, {json.dumps(project_name, ensure_ascii=False)})}} / ${{text(data.runId, RUN_ID)}}`;
      document.getElementById("detail-title").textContent = text(data.detailTitle, data.runId);
      document.getElementById("meta-run-id").textContent = `runId：${{text(data.runId, RUN_ID)}}`;
      document.getElementById("meta-run-root").textContent = `运行目录：${{text(data.runRoot)}}`;
      document.getElementById("meta-generated").textContent = `最后刷新：${{text(data.generatedAt)}}`;
      const favoriteButton = document.getElementById("favorite-btn");
      favoriteButton.textContent = data.favorite ? "取消收藏" : "加入收藏";
      favoriteButton.disabled = false;

      document.getElementById("summary-premise").textContent = text(data.sceneDraftPremiseZh, data.detailTitle);
      document.getElementById("summary-publish").textContent =
        data.publishStatus ? `发布状态：${{data.publishStatus}} / ${{text(data.publishedAt, "未记录时间")}}` : "当前没有发布回执。";
      const counts = data.sectionCounts || {{}};
      document.getElementById("summary-sections").textContent =
        `${{text(counts.available, "0")}} / ${{text(counts.total, "0")}}`;
      document.getElementById("summary-social-post").textContent =
        data.socialPostPreview ? `社媒文案：${{data.socialPostPreview}}` : "当前没有社媒文案摘要。";

      document.getElementById("summary-image-block").innerHTML = data.imageRoute
        ? `
            <a class="action-link" href="${{escapeHtml(text(data.imageRoute))}}" target="_blank" rel="noreferrer">
              <img class="preview-image" src="${{escapeHtml(text(data.imageRoute))}}" alt="${{escapeHtml(text(data.detailTitle, data.runId))}}" loading="lazy">
            </a>
            <span class="preview-path">${{escapeHtml(text(data.generatedImagePath))}}</span>
          `
        : '<div class="muted">当前没有可预览的生成图。</div>';

      const sections = Array.isArray(data.sections) ? data.sections : [];
      const expandedRawKeys = new Set(
        Array.from(document.querySelectorAll("details[data-raw-key]"))
          .filter((item) => item.open)
          .map((item) => item.dataset.rawKey)
          .filter((item) => Boolean(item))
      );
      document.getElementById("section-nav").innerHTML = sections.length
        ? sections.map((section) => `<a href="#${{escapeHtml(section.id)}}">${{escapeHtml(text(section.title))}}</a>`).join("")
        : '<div class="empty">当前没有可展示内容。</div>';
      document.getElementById("detail-sections").innerHTML = sections.length
        ? sections.map((section) => renderSection(section, expandedRawKeys)).join("")
        : '<section class="card"><div class="empty">当前没有可展示内容。</div></section>';
    }}

    async function loadSnapshot() {{
      try {{
        const response = await fetch(`/api/run-detail?runId=${{encodeURIComponent(RUN_ID)}}`, {{ cache: "no-store" }});
        if (!response.ok) {{
          throw new Error(`HTTP ${{response.status}}`);
        }}
        const data = await response.json();
        renderSnapshot(data);
      }} catch (error) {{
        document.getElementById("detail-sections").innerHTML =
          `<section class="card"><div class="empty">读取详情失败：${{escapeHtml(error.message)}}</div></section>`;
      }}
    }}

    document.getElementById("favorite-btn").addEventListener("click", async (event) => {{
      const button = event.currentTarget;
      if (!currentDetailSnapshot) return;
      button.disabled = true;
      try {{
        await submitJson("/api/toggle-favorite", {{
          kind: "run",
          runId: text(currentDetailSnapshot.runId, RUN_ID),
          runRoot: text(currentDetailSnapshot.runRoot, ""),
          label: text(currentDetailSnapshot.detailTitle, ""),
          sceneDraftPremiseZh: text(currentDetailSnapshot.sceneDraftPremiseZh, currentDetailSnapshot.detailTitle),
        }});
        await loadSnapshot();
      }} catch (error) {{
        button.disabled = false;
        throw error;
      }}
    }});
    document.getElementById("refresh-btn").addEventListener("click", loadSnapshot);
    loadSnapshot();
    window.setInterval(loadSnapshot, REFRESH_MS);
  </script>
</body>
</html>
"""
