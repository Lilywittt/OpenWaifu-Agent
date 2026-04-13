
    const refreshMs = 5000;
    let currentSnapshot = null;
    let selectedRunId = "";
    let historyFilter = "active";
    let initializedForm = false;
    let expandedRawKeys = new Set();
    let detailSuspendUntil = 0;

    function normalizeText(value) {
      return String(value || "").trim();
    }

    function rememberExpandedDetails() {
      expandedRawKeys = new Set(
        Array.from(document.querySelectorAll("details[data-raw-key][open]"))
          .map((element) => element.getAttribute("data-raw-key"))
          .filter(Boolean)
      );
    }

    function statusClass(status) {
      const normalized = normalizeText(status);
      if (["completed", "idle"].includes(normalized)) return "status-ok";
      if (["stopping", "interrupted"].includes(normalized)) return "status-warn";
      if (["failed"].includes(normalized)) return "status-danger";
      return "";
    }

    function applyActionMessage(text, kind = "") {
      const element = document.getElementById("action-message");
      element.textContent = text || "";
      element.className = "message" + (kind ? " " + kind : "");
    }

    function buildSourceKindMap(sourceKinds) {
      const map = new Map();
      (sourceKinds || []).forEach((item) => map.set(item.id, item));
      return map;
    }

    function ensureFormOptions(snapshot) {
      const config = snapshot?.config || {};
      const sourceKinds = Array.isArray(config.sourceKinds) ? config.sourceKinds : [];
      const sourceSelect = document.getElementById("source-kind");
      if (!sourceSelect.dataset.ready) {
        sourceSelect.innerHTML = sourceKinds
          .map((item) => `<option value="${item.id}">${item.label}</option>`)
          .join("");
        sourceSelect.dataset.ready = "1";
      }
      updateEndStageOptions(snapshot);
    }

    function updateEndStageOptions(snapshot, options = {}) {
      const sourceSelect = document.getElementById("source-kind");
      const endSelect = document.getElementById("end-stage");
      const sourceKinds = buildSourceKindMap(snapshot?.config?.sourceKinds || []);
      const sourceKind = normalizeText(sourceSelect.value);
      const sourceConfig = sourceKinds.get(sourceKind);
      const allowedStages = Array.isArray(sourceConfig?.allowedEndStages) ? sourceConfig.allowedEndStages : [];
      const previousValue = normalizeText(endSelect.value);
      endSelect.innerHTML = allowedStages
        .map((item) => `<option value="${item.id}">${item.label}</option>`)
        .join("");
      let nextValue = "";
      if (allowedStages.some((item) => item.id === previousValue)) {
        nextValue = previousValue;
      } else if (allowedStages.length) {
        nextValue = options.preferFirstStage ? allowedStages[0].id : allowedStages[allowedStages.length - 1].id;
      }
      endSelect.value = nextValue;
      updateSourceFields(snapshot);
    }

    function updateSourceFields(snapshot) {
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
    }

    function applyRequestToForm(request) {
      if (!request || typeof request !== "object") return;
      const sourceKind = normalizeText(request.sourceKind);
      const sourceSelect = document.getElementById("source-kind");
      if (sourceKind) sourceSelect.value = sourceKind;
      updateEndStageOptions(currentSnapshot || { config: { sourceKinds: [] } });
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
      updateSourceFields(currentSnapshot || { config: { sourceKinds: [] } });
    }

    function initializeDefaultForm(snapshot) {
      const sourceKinds = Array.isArray(snapshot?.config?.sourceKinds) ? snapshot.config.sourceKinds : [];
      const sourceSelect = document.getElementById("source-kind");
      if (!normalizeText(sourceSelect.value) && sourceKinds.length) {
        sourceSelect.value = sourceKinds[0].id;
      }
      updateEndStageOptions(snapshot);
      clearForm();
    }

    function clearForm() {
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
    }

    function collectRequestPayload() {
      return {
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
      };
    }

    function currentEndStageLabel() {
      const endSelect = document.getElementById("end-stage");
      const option = endSelect.options[endSelect.selectedIndex];
      return normalizeText(option?.text || endSelect.value);
    }

    async function submitJson(url, payload = null) {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload === null ? "{}" : JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({ ok: false, error: "返回结果不是合法 JSON。" }));
      if (!response.ok || !data.ok) {
        throw new Error(normalizeText(data.error) || "请求失败。");
      }
      return data;
    }

    function renderStatus(snapshot) {
      const status = snapshot?.status || {};
      const heroStatus = document.getElementById("hero-status");
      heroStatus.textContent = status.statusLabel || "未知";
      heroStatus.className = "pill " + statusClass(status.status);
      document.getElementById("meta-generated").textContent = `最后刷新：${snapshot.generatedAt || "-"}`;
      document.getElementById("meta-project").textContent = `项目目录：${snapshot.projectDir || "-"}`;
      document.getElementById("status-value").textContent = status.statusLabel || "未知";
      document.getElementById("status-value").className = "status-value " + statusClass(status.status);
      document.getElementById("status-stage").textContent = status.stage || "等待新测试";
      const request = status.request || {};
      const requestLabel = normalizeText(request.label) || "未命名测试";
      document.getElementById("status-stage-detail").textContent =
        request.sourceKind ? `起点：${request.sourceKind} · 终点：${request.endStage} · 标签：${requestLabel}` : "当前没有运行中的内容测试。";
      document.getElementById("status-run-id").textContent = `runId：${status.runId || "-"}`;
      document.getElementById("status-run-root").textContent = `运行目录：${status.runRoot || "-"}`;
      document.getElementById("status-slot").textContent = `执行位：${status.generationSlotText || "空闲"}`;
      const statusError = document.getElementById("status-error");
      const shouldShowError = ["failed", "interrupted"].includes(normalizeText(status.status)) && normalizeText(status.error);
      if (shouldShowError) {
        statusError.style.display = "";
        statusError.textContent = status.error;
      } else {
        statusError.style.display = "none";
        statusError.textContent = "";
      }
      document.getElementById("start-btn").disabled = !status.canStart;
      document.getElementById("stop-btn").disabled = !status.canStop;
      document.getElementById("rerun-btn").disabled = !status.canStart;
    }

    function filteredHistory(snapshot) {
      const history = Array.isArray(snapshot?.history) ? snapshot.history : [];
      if (historyFilter === "deleted") {
        return history.filter((item) => item.deleted);
      }
      if (historyFilter === "all") {
        return history;
      }
      return history.filter((item) => !item.deleted);
    }

    function historySelectionList(snapshot) {
      const items = [];
      const seen = new Set();
      const currentRunItem = snapshot?.currentRunItem;
      const history = filteredHistory(snapshot);
      if (currentRunItem && !currentRunItem.deleted) {
        const currentKey = normalizeText(currentRunItem.selectionKey || currentRunItem.runId);
        if (currentKey) {
          items.push(currentRunItem);
          seen.add(currentKey);
        }
      }
      history.forEach((item) => {
        const key = normalizeText(item.selectionKey || item.runId);
        if (!key || seen.has(key)) return;
        items.push(item);
        seen.add(key);
      });
      return items;
    }

    function activeSelectionKey(snapshot) {
      const currentRunItem = snapshot?.currentRunItem;
      if (currentRunItem) {
        return normalizeText(currentRunItem.selectionKey || currentRunItem.runId);
      }
      return "";
    }

    function suspendDetailRefresh(milliseconds = 6000) {
      detailSuspendUntil = Math.max(detailSuspendUntil, Date.now() + Math.max(Number(milliseconds) || 0, 0));
    }

    function shouldRenderDetail(snapshot, options = {}) {
      if (options.forceDetail || !currentSnapshot) {
        return true;
      }
      const nextSelection = normalizeText(snapshot?.selectedRunId);
      const previousSelection = normalizeText(currentSnapshot?.selectedRunId);
      if (nextSelection !== previousSelection) {
        return true;
      }
      if (!nextSelection) {
        return false;
      }
      const activeKey = activeSelectionKey(snapshot);
      if (!activeKey || nextSelection !== activeKey) {
        return false;
      }
      if (Date.now() < detailSuspendUntil) {
        return false;
      }
      return true;
    }

    async function moveHistorySelection(step) {
      const history = historySelectionList(currentSnapshot);
      if (!history.length) return;
      const currentKey = normalizeText(selectedRunId);
      const currentIndex = history.findIndex((item) => normalizeText(item.selectionKey || item.runId) === currentKey);
      let nextIndex = 0;
      if (currentIndex >= 0) {
        nextIndex = Math.min(Math.max(currentIndex + step, 0), history.length - 1);
      } else if (step < 0) {
        nextIndex = history.length - 1;
      }
      selectedRunId = normalizeText(history[nextIndex]?.selectionKey || history[nextIndex]?.runId);
      detailSuspendUntil = 0;
      await fetchSnapshot({ forceDetail: true });
    }

    async function jumpHistorySelection(target) {
      const history = historySelectionList(currentSnapshot);
      if (!history.length) return;
      const index = target === "end" ? history.length - 1 : 0;
      selectedRunId = normalizeText(history[index]?.selectionKey || history[index]?.runId);
      detailSuspendUntil = 0;
      await fetchSnapshot({ forceDetail: true });
    }

    function renderHistorySummary(snapshot) {
      const stats = snapshot?.historyStats || {};
      const running = Number(stats.running || 0);
      const active = Number(stats.active || 0);
      const deleted = Number(stats.deleted || 0);
      const total = Number(stats.total || 0);
      document.getElementById("history-summary").textContent = `当前 ${running} · 有效 ${active} · 已删除 ${deleted} · 总计 ${total}`;
      document.getElementById("history-filter-active").classList.toggle("active", historyFilter === "active");
      document.getElementById("history-filter-all").classList.toggle("active", historyFilter === "all");
      document.getElementById("history-filter-deleted").classList.toggle("active", historyFilter === "deleted");
    }

    function renderHistory(snapshot) {
      renderHistorySummary(snapshot);
      const currentGroup = document.getElementById("current-run-group");
      const currentRoot = document.getElementById("current-run-list");
      const historyRoot = document.getElementById("history-list");
      const currentRunItem = snapshot?.currentRunItem && !snapshot.currentRunItem.deleted ? snapshot.currentRunItem : null;
      const history = filteredHistory(snapshot).filter((item) => normalizeText(item.selectionKey || item.runId) !== normalizeText(currentRunItem?.selectionKey || currentRunItem?.runId));

      const renderItems = (items) => items.map((item) => {
        const selectionKey = item.selectionKey || item.runId || "";
        const isActive = selectionKey && selectionKey === snapshot.selectedRunId;
        const title = item.sceneDraftPremiseZh || item.label || "未命名测试";
        const secondary = `${item.sourceKindLabel || item.sourceKind || "-"} → ${item.endStageLabel || item.endStage || "-"}`;
        const errorLine = item.error ? `<div class="muted">错误：${item.error}</div>` : "";
        const runIdLine = item.runId ? `<div class="mono muted">runId：${item.runId}</div>` : "";
        const timeLabel = item.deleted ? "删除时间" : "记录时间";
        const thumb = item.imageRoute && !item.deleted
          ? `<img class="history-thumb" src="${item.imageRoute}" alt="${title}" loading="lazy" />`
          : `<div class="history-thumb empty">${item.deleted ? "已删" : "暂无图"}</div>`;
        return `
          <li class="history-item${isActive ? " active" : ""}${item.deleted ? " deleted" : ""}" data-history-select="${selectionKey}" tabindex="0">
            <div class="history-main">
              <div>
                <div class="history-top">
                  <div>
                    <div class="history-title">${title}</div>
                    <div class="muted">${secondary}</div>
                  </div>
                  <span class="badge ${statusClass(item.status)}">${item.statusLabel || item.status || "未知"}</span>
                </div>
                <div class="history-meta">
                  <div>${timeLabel}：${item.displayTime || "-"}</div>
                  ${runIdLine}
                  ${errorLine}
                </div>
              </div>
              <div>${thumb}</div>
            </div>
            <div class="history-foot">
              <div class="muted">${item.deleted ? "目录已删除，索引保留供回看。" : "点击卡片即可切换详情。"}</div>
            </div>
          </li>
        `;
      }).join("");

      currentGroup.hidden = !currentRunItem;
      currentRoot.innerHTML = currentRunItem ? renderItems([currentRunItem]) : "";
      if (!history.length) {
        historyRoot.innerHTML = '<li class="empty">当前筛选下没有测试记录。</li>';
      } else {
        historyRoot.innerHTML = renderItems(history);
      }

      document.querySelectorAll("[data-history-select]").forEach((element) => {
        element.addEventListener("click", (event) => {
          const key = normalizeText(element.getAttribute("data-history-select"));
          if (!key) return;
          event.preventDefault();
          event.stopPropagation();
          selectedRunId = key;
          detailSuspendUntil = 0;
          fetchSnapshot({ forceDetail: true });
        });
        element.addEventListener("keydown", (event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          const key = normalizeText(element.getAttribute("data-history-select"));
          if (!key) return;
          event.preventDefault();
          selectedRunId = key;
          detailSuspendUntil = 0;
          fetchSnapshot({ forceDetail: true });
        });
      });
    }

    function escapeHtml(value) {
      return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function renderMetaRows(rows) {
      if (!Array.isArray(rows) || !rows.length) return "";
      return `<div class="section-meta">${rows.map((row) => `<span>${escapeHtml(row.label)}：${escapeHtml(row.value)}</span>`).join("")}</div>`;
    }

    function renderCompareBlocks(section) {
      const compareBlocks = Array.isArray(section.compareBlocks) ? section.compareBlocks : [];
      if (!compareBlocks.length) return "";
      return `
        <div class="diff-blocks">
          ${compareBlocks.map((block) => {
            const variant = normalizeText(block.variant) === "after" ? "after" : "before";
            const segments = Array.isArray(block.segments) ? block.segments : [];
            const contentHtml = segments.length
              ? `<div class="diff-content">${segments.map((segment) => {
                  const changedClass = segment.changed ? ` changed ${variant}` : "";
                  return `<span class="diff-token${changedClass}">${escapeHtml(segment.text || "")}</span>`;
                }).join("")}</div>`
              : '<div class="empty">当前没有可展示的内容。</div>';
            return `
              <div class="diff-block">
                <div class="diff-title">${escapeHtml(block.title || "")}</div>
                ${contentHtml}
              </div>
            `;
          }).join("")}
        </div>
      `;
    }

    function renderSection(section, runId) {
      const rawKey = `${runId}:${section.id}`;
      const isOpen = expandedRawKeys.has(rawKey);
      const bullets = Array.isArray(section.bullets) ? section.bullets : [];
      const bulletHtml = bullets.length ? `<ul>${bullets.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : "";
      const compareHtml = renderCompareBlocks(section);
      const rawArea = section.rawText ? `
        <div class="raw-toggle">
          <details data-raw-key="${escapeHtml(rawKey)}"${isOpen ? " open" : ""}>
            <summary>查看原始文件内容</summary>
            <pre>${escapeHtml(section.rawText)}</pre>
          </details>
        </div>
      ` : "";
      const errorText = section.error ? `<div class="muted status-danger">解析提示：${escapeHtml(section.error)}</div>` : "";
      const truncatedText = section.truncated ? '<div class="muted">原始内容过长，面板已截断展示。</div>' : "";
      return `
        <article class="section-card" id="section-${escapeHtml(section.id)}">
          <h3>${escapeHtml(section.title)}</h3>
          <div class="mono muted">${escapeHtml(section.path || "-")}</div>
          ${renderMetaRows(section.metaRows)}
          ${compareHtml || (section.bodyText ? `<div class="section-text">${escapeHtml(section.bodyText)}</div>` : '<div class="empty">当前没有可展示的正文。</div>')}
          ${bulletHtml}
          ${errorText}
          ${truncatedText}
          ${rawArea}
        </article>
      `;
    }

    function selectedHistoryItem(snapshot) {
      const currentKey = normalizeText(snapshot?.selectedRunId);
      return historySelectionList(snapshot).find((item) => normalizeText(item.selectionKey || item.runId) === currentKey) || null;
    }

    async function deleteRunById(runId) {
      if (!runId) return;
      if (!window.confirm(`确认删除这轮测试的整个目录吗？\n\n${runId}`)) return;
      applyActionMessage("正在删除测试目录…");
      await submitJson("/api/delete-run", { runId });
      if (selectedRunId === runId) {
        selectedRunId = "";
      }
      applyActionMessage(`已删除目录：${runId}`, "success");
      detailSuspendUntil = 0;
      await fetchSnapshot({ forceDetail: true });
    }

    function renderDetailActions(snapshot, detail, selectedItem) {
      const root = document.getElementById("detail-actions");
      const history = historySelectionList(snapshot);
      const currentKey = normalizeText(snapshot?.selectedRunId);
      const index = history.findIndex((item) => normalizeText(item.selectionKey || item.runId) === currentKey);
      const previousItem = index > 0 ? history[index - 1] : null;
      const nextItem = index >= 0 && index < history.length - 1 ? history[index + 1] : null;
      const canDelete = !!normalizeText(detail?.runId);
      root.innerHTML = `
        <button type="button" data-detail-nav="prev" ${previousItem ? "" : "disabled"}>上一条</button>
        <button type="button" data-detail-nav="next" ${nextItem ? "" : "disabled"}>下一条</button>
        ${canDelete ? '<button type="button" class="danger" data-detail-delete="current">删除当前目录</button>' : ""}
      `;
      root.querySelectorAll("[data-detail-nav]").forEach((button) => {
        button.addEventListener("click", async () => {
          const direction = normalizeText(button.getAttribute("data-detail-nav"));
          const target = direction === "prev" ? previousItem : nextItem;
          const key = normalizeText(target?.selectionKey || target?.runId);
          if (!key) return;
          selectedRunId = key;
          detailSuspendUntil = 0;
          await fetchSnapshot({ forceDetail: true });
        });
      });
      const deleteButton = root.querySelector("[data-detail-delete='current']");
      if (deleteButton) {
        deleteButton.addEventListener("click", async () => {
          await deleteRunById(normalizeText(detail?.runId));
        });
      }
    }

    function renderDetail(snapshot) {
      const detail = snapshot?.selectedRunDetail;
      const root = document.getElementById("detail-root");
      const badge = document.getElementById("detail-badge");
      const selectedItem = selectedHistoryItem(snapshot);
      renderDetailActions(snapshot, detail, selectedItem);
      if (!detail) {
        const status = snapshot?.status || {};
        if (selectedItem?.deleted) {
          badge.textContent = "目录已删除";
          root.className = "";
          root.innerHTML = `
            <div class="detail-summary">
              <div class="history-title">${escapeHtml(selectedItem.sceneDraftPremiseZh || selectedItem.label || selectedItem.runId || "已删除测试")}</div>
              <div class="summary-meta">
                <span>runId：${escapeHtml(selectedItem.runId || "-")}</span>
                <span>删除时间：${escapeHtml(selectedItem.deletedAt || selectedItem.displayTime || "-")}</span>
              </div>
              <div class="muted">该测试目录已经删除，左侧索引项仅用于人工回看与筛选记录。</div>
            </div>
          `;
          return;
        }
        if (status.busy) {
          badge.textContent = "当前测试运行中";
          root.className = "empty";
          root.innerHTML = "当前测试已经启动，正在准备运行目录或等待第一批产物。<br />左侧最上方会保留当前运行项，可随时切回。";
          return;
        }
        badge.textContent = "未选择测试";
        root.className = "empty";
        root.textContent = "开始一轮测试后，这里会实时展开它的中间产物和最终产物。";
        return;
      }
      badge.textContent = detail.detailTitle || detail.runId || "当前测试";
      const imagePanel = detail.imageRoute
        ? `
          <a class="preview-link" href="${detail.imageRoute}" target="_blank" rel="noreferrer">
            <img class="preview-image" src="${detail.imageRoute}" alt="${escapeHtml(detail.detailTitle || detail.runId)}" />
            <span class="muted">点击查看大图</span>
          </a>
        `
        : '<div class="empty">当前还没有最终图片。</div>';
      const sections = Array.isArray(detail.sections) ? detail.sections : [];
      const sectionsHtml = sections.map((section) => renderSection(section, detail.runId)).join("");
      const sectionNav = sections.length
        ? `
          <div class="section-nav">
            ${sections.map((section) => `<a href="#section-${escapeHtml(section.id)}">${escapeHtml(section.title)}</a>`).join("")}
          </div>
        `
        : "";
      root.className = "";
      root.innerHTML = `
        <div class="detail-hero">
          <div class="detail-summary">
            <div class="history-title">${escapeHtml(detail.detailTitle || detail.runId)}</div>
            <div class="summary-meta">
              <span>runId：${escapeHtml(detail.runId || "-")}</span>
              <span>运行目录：${escapeHtml(detail.runRoot || "-")}</span>
              <span>可用内容：${detail.sectionCounts?.available || 0} / ${detail.sectionCounts?.total || 0}</span>
            </div>
            <div class="muted">${escapeHtml(detail.socialPostPreview || "当前还没有社媒文案预览。")}</div>
            <div class="mono muted">${escapeHtml(detail.summaryPath || "")}</div>
          </div>
          <div>${imagePanel}</div>
        </div>
        ${sectionNav}
        <div class="section-grid" style="margin-top: 18px;">${sectionsHtml || '<div class="empty">当前没有可展示的中间产物。</div>'}</div>
      `;
    }

    async function fetchSnapshot(options = {}) {
      rememberExpandedDetails();
      const query = selectedRunId ? `?selectedRunId=${encodeURIComponent(selectedRunId)}` : "";
      const response = await fetch(`/api/snapshot${query}`, { cache: "no-store" });
      const snapshot = await response.json();
      if (!normalizeText(snapshot?.selectedRunId) && snapshot?.status?.busy) {
        const activeItem = snapshot?.currentRunItem;
        if (activeItem) {
          snapshot.selectedRunId = normalizeText(activeItem.selectionKey || activeItem.runId);
        }
      }
      const currentActiveKey = activeSelectionKey(snapshot);
      if (normalizeText(snapshot?.selectedRunId) === "__active__" && currentActiveKey && currentActiveKey !== "__active__") {
        snapshot.selectedRunId = currentActiveKey;
      }
      const detailWasRendered = shouldRenderDetail(snapshot, options);
      selectedRunId = normalizeText(snapshot?.selectedRunId);
      currentSnapshot = snapshot;
      document.getElementById("hero-title").textContent = snapshot?.identity?.workbenchTitle || "单小伊 Agent 内容测试工作台";
      ensureFormOptions(snapshot);
      if (!initializedForm) {
        initializeDefaultForm(snapshot);
        initializedForm = true;
      }
      renderStatus(snapshot);
      renderHistory(snapshot);
      if (detailWasRendered) {
        renderDetail(snapshot);
      }
    }

    document.getElementById("source-kind").addEventListener("change", () => {
      updateEndStageOptions(currentSnapshot);
    });
    const detailRoot = document.getElementById("detail-root");
    ["wheel", "pointerdown", "focusin"].forEach((eventName) => {
      detailRoot.addEventListener(eventName, () => {
        suspendDetailRefresh();
      });
    });
    document.getElementById("refresh-btn").addEventListener("click", async () => {
      detailSuspendUntil = 0;
      await fetchSnapshot({ forceDetail: true });
    });
    document.getElementById("history-filter-active").addEventListener("click", () => {
      historyFilter = "active";
      renderHistory(currentSnapshot);
      renderDetail(currentSnapshot);
    });
    document.getElementById("history-filter-all").addEventListener("click", () => {
      historyFilter = "all";
      renderHistory(currentSnapshot);
      renderDetail(currentSnapshot);
    });
    document.getElementById("history-filter-deleted").addEventListener("click", () => {
      historyFilter = "deleted";
      renderHistory(currentSnapshot);
      renderDetail(currentSnapshot);
    });
    document.getElementById("fill-last-btn").addEventListener("click", () => {
      applyRequestToForm(currentSnapshot?.lastRequest || {});
      applyActionMessage("已载入上一次请求。", "success");
    });
    document.getElementById("clear-form-btn").addEventListener("click", () => {
      clearForm();
      applyActionMessage("输入区已清空。", "success");
    });
    document.getElementById("start-btn").addEventListener("click", async () => {
      try {
        applyActionMessage("正在启动测试…");
        await submitJson("/api/start", collectRequestPayload());
        selectedRunId = "__active__";
        applyActionMessage("测试已启动。", "success");
        detailSuspendUntil = 0;
        await fetchSnapshot({ forceDetail: true });
      } catch (error) {
        applyActionMessage(error.message || "启动测试失败。", "error");
      }
    });
    document.getElementById("stop-btn").addEventListener("click", async () => {
      try {
        applyActionMessage("正在请求停止当前测试…");
        const data = await submitJson("/api/stop");
        applyActionMessage(data.alreadyStopping ? "停止请求已在处理中。" : "已发送停止请求。", "success");
        detailSuspendUntil = 0;
        await fetchSnapshot({ forceDetail: true });
      } catch (error) {
        applyActionMessage(error.message || "停止测试失败。", "error");
      }
    });
    document.getElementById("rerun-btn").addEventListener("click", async () => {
      try {
        applyActionMessage("正在复跑上一轮请求…");
        await submitJson("/api/rerun-last");
        selectedRunId = "__active__";
        applyActionMessage("已开始复跑上一轮测试。", "success");
        detailSuspendUntil = 0;
        await fetchSnapshot({ forceDetail: true });
      } catch (error) {
        applyActionMessage(error.message || "复跑失败。", "error");
      }
    });
    document.addEventListener("keydown", async (event) => {
      const target = event.target;
      const tagName = String(target?.tagName || "").toLowerCase();
      const isEditing =
        tagName === "input" ||
        tagName === "textarea" ||
        tagName === "select" ||
        Boolean(target?.isContentEditable);
      if (isEditing || event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key === "ArrowUp") {
        event.preventDefault();
        await moveHistorySelection(-1);
      } else if (event.key === "ArrowDown") {
        event.preventDefault();
        await moveHistorySelection(1);
      } else if (event.key === "Home") {
        event.preventDefault();
        await jumpHistorySelection("start");
      } else if (event.key === "End") {
        event.preventDefault();
        await jumpHistorySelection("end");
      }
    });

    fetchSnapshot().catch((error) => {
      applyActionMessage(error.message || "读取面板状态失败。", "error");
    });
    setInterval(() => {
      fetchSnapshot().catch(() => null);
    }, refreshMs);
  
